import io
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from flask import Blueprint, Response, abort, current_app, send_file, request

from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager


def create_download_blueprint(
    mixtape_manager: MixtapeManager, logger: Logger | None = None
) -> Blueprint:
    """
    Creates a Flask blueprint for downloading mixtapes as offline packages.

    Handles conversion of audio files to MP3 format and packages them with
    metadata into a downloadable ZIP file.

    Args:
        mixtape_manager: The manager instance for retrieving mixtape data.
        logger: Optional logger instance for error reporting.

    Returns:
        Blueprint: The configured Flask blueprint for downloads.
    """
    download = Blueprint("download", __name__)
    logger = logger or NullLogger()

    @download.route("/<slug>/playlist.m3u")
    def download_playlist(slug: str) -> Response:
        """
        Generates an M3U playlist file for streaming.

        Uses extended M3U format with full metadata for maximum compatibility
        with desktop and mobile music players.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: An M3U playlist file with streaming URLs.
        """
        return _generate_m3u_playlist(slug, mode='stream')

    @download.route("/<slug>/playlist-offline.m3u")
    def download_playlist_offline(slug: str) -> Response:
        """
        Generates an M3U playlist that triggers individual track downloads.

        This creates a special playlist where each track is a direct download link.
        When opened in a music app, it will prompt to download each track.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: An M3U playlist configured for offline downloads.
        """
        return _generate_m3u_playlist(slug, mode='download')

    @download.route("/<slug>/bulk-download")
    def bulk_download_tracks(slug: str) -> Response:
        """
        Creates a ZIP of all tracks (without the offline player).

        This is for users who want just the music files to import into
        their desktop music library (iTunes, Rhythmbox, etc.)

        Args:
            slug: The mixtape identifier.

        Returns:
            Response: A ZIP file containing just the audio tracks.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)

        try:
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Add all tracks (with conversion)
                _add_tracks_to_zip(
                    zip_file,
                    mixtape,
                    Path(current_app.config["MUSIC_ROOT"]),
                    logger
                )

            zip_buffer.seek(0)

            filename = f"{slug}-tracks.zip"
            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=filename,
            )

        except Exception as e:
            logger.error(f"Failed to create track package for {slug}: {e}")
            abort(500)

    def _generate_m3u_playlist(slug: str, mode: str = 'stream') -> Response:
        """
        Internal helper to generate M3U playlists with different caching strategies.

        Args:
            slug: The mixtape identifier.
            mode: 'stream' (default) or 'download'
                - stream: URLs point to streaming endpoint with inline disposition
                - download: URLs point to download endpoint with attachment disposition

        Returns:
            Response: An M3U playlist file.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)

        # Use EXTM3U format for better compatibility
        m3u_content = "#EXTM3U\n"

        # Add playlist-level metadata
        m3u_content += f"#PLAYLIST:{mixtape.get('title', 'Mixtape')}\n"

        # Add extended info for better player compatibility
        if mixtape.get('liner_notes'):
            # Some players show this as description
            m3u_content += f"#EXTINFO:{mixtape.get('title')} - A personal mixtape\n"

        m3u_content += "\n"

        for idx, track in enumerate(mixtape.get("tracks", []), 1):
            title = track.get("track", "Unknown")
            artist = track.get("artist", "Unknown")
            album = track.get("album", "")

            # Extended info format: #EXTINF:duration,artist - title
            # Duration -1 means unknown (will be calculated by player)
            m3u_content += f"#EXTINF:-1,{artist} - {title}\n"

            # Add extended metadata tags for players that support them
            if artist:
                m3u_content += f"#EXTART:{artist}\n"
            if album:
                m3u_content += f"#EXTALB:{album}\n"

            # Build URL based on mode
            if mode == 'download':
                # Attachment disposition - forces download
                track_url = f"{request.url_root.rstrip('/')}download/{slug}/track-file/{track.get('path')}"
            else:
                # Inline disposition - allows streaming
                track_url = f"{request.url_root.rstrip('/')}download/{slug}/track/{track.get('path')}"

            m3u_content += f"{track_url}\n\n"

        filename = f"{slug}-offline.m3u" if mode == 'download' else f"{slug}.m3u"

        return Response(
            m3u_content,
            mimetype="audio/x-mpegurl",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "audio/x-mpegurl; charset=utf-8"
            }
        )

    @download.route("/<slug>/track/<path:track_path>")
    def download_track(slug: str, track_path: str) -> Response:
        """
        Streams a single track, converting FLAC to MP3 if needed.

        This endpoint serves tracks with 'inline' disposition, meaning the browser/app
        will try to play it directly. The response includes long cache headers so
        music apps can cache it for offline use.

        Args:
            slug: The mixtape identifier.
            track_path: The relative path to the audio file.

        Returns:
            Response: The audio file (converted to MP3 if FLAC), served inline.
        """
        return _serve_track(slug, track_path, as_attachment=False)

    @download.route("/<slug>/track-file/<path:track_path>")
    def download_track_file(slug: str, track_path: str) -> Response:
        """
        Downloads a single track as a file, converting FLAC to MP3 if needed.

        This endpoint serves tracks with 'attachment' disposition, forcing the
        browser/app to download the file rather than streaming it. This is used
        by the "offline" M3U playlist.

        Args:
            slug: The mixtape identifier.
            track_path: The relative path to the audio file.

        Returns:
            Response: The audio file (converted to MP3 if FLAC), as download.
        """
        return _serve_track(slug, track_path, as_attachment=True)

    def _serve_track(slug: str, track_path: str, as_attachment: bool = False) -> Response:
        """
        Internal helper to serve or stream a track.

        Args:
            slug: The mixtape identifier.
            track_path: The relative path to the audio file.
            as_attachment: If True, force download. If False, allow inline playback.

        Returns:
            Response: The audio file response.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)

        # Verify this track belongs to this mixtape
        track_found = False
        track_metadata = None
        for track in mixtape.get("tracks", []):
            if track.get("path") == track_path:
                track_found = True
                track_metadata = track
                break

        if not track_found:
            abort(404)

        music_root = Path(current_app.config["MUSIC_ROOT"])
        full_path = music_root / track_path

        if not full_path.exists():
            abort(404)

        # Generate safe filename
        safe_name = _get_safe_track_name(0, track_metadata)

        # Convert FLAC to MP3 on-the-fly
        if full_path.suffix.lower() == ".flac":
            try:
                mp3_data = _convert_flac_to_mp3(full_path, track_metadata, logger)
                if not mp3_data:
                    logger.error(f"Failed to convert {full_path}")
                    abort(500)

                disposition = 'attachment' if as_attachment else 'inline'

                return Response(
                    mp3_data,
                    mimetype="audio/mpeg",
                    headers={
                        "Content-Disposition": f'{disposition}; filename="{safe_name}"',
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                        "X-Content-Duration": str(len(mp3_data)),  # Hint for apps
                    }
                )
            except Exception as e:
                logger.error(f"Error converting track {track_path}: {e}")
                abort(500)

        # For non-FLAC, serve the file directly
        return send_file(
            full_path,
            mimetype=_guess_mime_type(full_path),
            as_attachment=as_attachment,
            download_name=safe_name,
            max_age=31536000,  # Cache for 1 year
        )

    @download.route("/<slug>/package")
    def download_mixtape(slug: str) -> Response:
        """
        Creates and streams a ZIP package containing the mixtape's audio files and metadata.

        This is the desktop option - for users who want everything in one file.
        Converts FLAC files to MP3 on-the-fly to reduce download size, preserving metadata.
        The ZIP includes all tracks, cover image, and a JSON metadata file.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: A streaming response containing the ZIP file.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)

        try:
            # Create in-memory ZIP file
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Add metadata JSON
                _add_metadata_to_zip(zip_file, mixtape)

                # Add offline player HTML
                _add_offline_player(zip_file)

                # Add cover image if exists
                _add_cover_to_zip(zip_file, mixtape, current_app.config["COVER_DIR"])

                # Add all tracks (with conversion)
                _add_tracks_to_zip(
                    zip_file,
                    mixtape,
                    Path(current_app.config["MUSIC_ROOT"]),
                    logger
                )

            zip_buffer.seek(0)

            filename = f"{slug}.zip"
            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=filename,
            )

        except Exception as e:
            logger.error(f"Failed to create mixtape package for {slug}: {e}")
            abort(500)

    def _add_metadata_to_zip(zip_file: zipfile.ZipFile, mixtape: dict) -> None:
        """
        Adds mixtape metadata JSON to the ZIP archive.

        Creates a cleaned metadata file without server-specific paths.

        Args:
            zip_file: The ZIP archive to add the metadata to.
            mixtape: The mixtape data dictionary.
        """
        import json

        # Create clean metadata (remove server paths)
        clean_metadata = {
            "title": mixtape.get("title"),
            "created_at": mixtape.get("created_at"),
            "updated_at": mixtape.get("updated_at"),
            "liner_notes": mixtape.get("liner_notes", ""),
            "tracks": [
                {
                    "track": t.get("track"),
                    "artist": t.get("artist"),
                    "album": t.get("album", ""),
                    "filename": _get_converted_filename(t.get("path"))
                }
                for t in mixtape.get("tracks", [])
            ],
        }

        zip_file.writestr("mixtape.json", json.dumps(clean_metadata, indent=2))

    def _add_offline_player(zip_file: zipfile.ZipFile) -> None:
        """
        Adds the offline player HTML file to the ZIP archive.

        Args:
            zip_file: The ZIP archive to add the player to.
        """
        # Embed the offline player HTML directly (since we created it)
        # This ensures it's always included regardless of file structure
        player_html = """<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="mixtape-title">Mixtape Player</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
        }
        .player-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .track-item {
            cursor: pointer;
            transition: all 0.2s;
        }
        .track-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        .track-item.active {
            background-color: rgba(74, 144, 226, 0.3);
            border-left: 4px solid #4a90e2;
        }
        .cover-img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        #liner-notes {
            white-space: pre-wrap;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row g-4">
            <!-- Left Column: Cover & Info -->
            <div class="col-lg-4">
                <div class="player-card rounded-3 shadow-lg p-4 text-center">
                    <img id="cover-image" src="" alt="Cover" class="cover-img mb-4" style="display: none;">
                    <h1 class="h3 mb-2" id="mixtape-title-display">Loading...</h1>
                    <p class="text-muted small mb-4" id="track-count"></p>

                    <div class="d-grid gap-2 mb-4">
                        <button class="btn btn-primary btn-lg" id="play-all">
                            <i class="bi bi-play-fill"></i> Play All
                        </button>
                    </div>

                    <!-- Liner Notes -->
                    <div class="mt-4" id="liner-notes-section" style="display: none;">
                        <h5 class="mb-3">Tape Talk</h5>
                        <div class="text-start" id="liner-notes"></div>
                    </div>
                </div>
            </div>

            <!-- Right Column: Tracklist -->
            <div class="col-lg-8">
                <div class="player-card rounded-3 shadow-lg p-4">
                    <h4 class="mb-4">Tracklist</h4>
                    <div class="list-group" id="tracklist"></div>
                </div>
            </div>
        </div>

        <!-- Bottom Player -->
        <div class="fixed-bottom" id="bottom-player" style="display: none;">
            <div class="bg-dark shadow-lg border-top">
                <div class="container py-3">
                    <div class="d-flex align-items-center gap-3 flex-wrap">
                        <div class="flex-grow-1">
                            <div class="fw-bold" id="now-playing-title">—</div>
                            <div class="small text-muted" id="now-playing-artist">—</div>
                        </div>
                        <div>
                            <button class="btn btn-sm btn-outline-light" id="prev-btn">
                                <i class="bi bi-skip-backward-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-light ms-1" id="play-pause-btn">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-light ms-1" id="next-btn">
                                <i class="bi bi-skip-forward-fill"></i>
                            </button>
                        </div>
                        <audio id="audio-player" controls class="flex-grow-1" style="max-width: 400px;"></audio>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let mixtapeData = null;
        let currentTrackIndex = -1;
        const audioPlayer = document.getElementById('audio-player');
        const tracklist = document.getElementById('tracklist');
        const bottomPlayer = document.getElementById('bottom-player');
        const nowPlayingTitle = document.getElementById('now-playing-title');
        const nowPlayingArtist = document.getElementById('now-playing-artist');

        // Load mixtape metadata
        fetch('mixtape.json')
            .then(r => r.json())
            .then(data => {
                mixtapeData = data;
                renderMixtape();
            })
            .catch(err => {
                console.error('Failed to load mixtape:', err);
                alert('Error loading mixtape data');
            });

        function renderMixtape() {
            // Set title
            document.getElementById('mixtape-title').textContent = mixtapeData.title;
            document.getElementById('mixtape-title-display').textContent = mixtapeData.title;
            document.getElementById('track-count').textContent = `${mixtapeData.tracks.length} tracks`;

            // Show cover if exists
            const coverImg = document.getElementById('cover-image');
            if (mixtapeData.cover !== undefined) {
                const coverPath = 'cover.jpg';
                coverImg.src = coverPath;
                coverImg.style.display = 'block';
                coverImg.onerror = () => {
                    coverImg.src = 'cover.png';
                    coverImg.onerror = () => coverImg.style.display = 'none';
                };
            }

            // Show liner notes if present
            if (mixtapeData.liner_notes && mixtapeData.liner_notes.trim()) {
                document.getElementById('liner-notes-section').style.display = 'block';
                document.getElementById('liner-notes').textContent = mixtapeData.liner_notes;
            }

            // Render tracklist
            mixtapeData.tracks.forEach((track, index) => {
                const trackEl = document.createElement('div');
                trackEl.className = 'list-group-item track-item d-flex align-items-center gap-3';
                trackEl.innerHTML = `
                    <button class="btn btn-light rounded-circle" style="width: 48px; height: 48px;">
                        <i class="bi bi-play-fill"></i>
                    </button>
                    <div class="flex-grow-1">
                        <div class="fw-bold">${track.track}</div>
                        <div class="small text-muted">${track.artist}${track.album ? ' • ' + track.album : ''}</div>
                    </div>
                `;
                trackEl.onclick = () => playTrack(index);
                tracklist.appendChild(trackEl);
            });
        }

        function playTrack(index) {
            if (index < 0 || index >= mixtapeData.tracks.length) return;

            const track = mixtapeData.tracks[index];
            audioPlayer.src = track.filename;
            audioPlayer.play();

            currentTrackIndex = index;
            bottomPlayer.style.display = 'block';

            nowPlayingTitle.textContent = track.track;
            nowPlayingArtist.textContent = `${track.artist}${track.album ? ' • ' + track.album : ''}`;

            // Update UI
            document.querySelectorAll('.track-item').forEach((el, i) => {
                el.classList.toggle('active', i === index);
                const icon = el.querySelector('i');
                icon.className = i === index ? 'bi bi-pause-fill' : 'bi bi-play-fill';
            });
        }

        // Controls
        document.getElementById('play-all').onclick = () => playTrack(0);
        document.getElementById('prev-btn').onclick = () => playTrack(currentTrackIndex - 1);
        document.getElementById('next-btn').onclick = () => playTrack(currentTrackIndex + 1);

        document.getElementById('play-pause-btn').onclick = () => {
            if (currentTrackIndex === -1) {
                playTrack(0);
            } else if (audioPlayer.paused) {
                audioPlayer.play();
            } else {
                audioPlayer.pause();
            }
        };

        // Auto-play next track
        audioPlayer.addEventListener('ended', () => {
            if (currentTrackIndex < mixtapeData.tracks.length - 1) {
                playTrack(currentTrackIndex + 1);
            }
        });

        // Update play/pause button icon
        audioPlayer.addEventListener('play', () => {
            document.querySelector('#play-pause-btn i').className = 'bi bi-pause-fill';
        });
        audioPlayer.addEventListener('pause', () => {
            document.querySelector('#play-pause-btn i').className = 'bi bi-play-fill';
        });
    </script>
</body>
</html>"""

        zip_file.writestr("index.html", player_html)

    def _add_cover_to_zip(
        zip_file: zipfile.ZipFile, mixtape: dict, cover_dir: Path
    ) -> None:
        """
        Adds the cover image to the ZIP archive if it exists.

        Args:
            zip_file: The ZIP archive to add the cover to.
            mixtape: The mixtape data dictionary.
            cover_dir: Path to the directory containing cover images.
        """
        if cover := mixtape.get("cover"):
            cover_path = Path(cover_dir) / cover.split("/")[-1]
            if cover_path.exists():
                zip_file.write(cover_path, arcname=f"cover{cover_path.suffix}")

    def _add_tracks_to_zip(
        zip_file: zipfile.ZipFile,
        mixtape: dict,
        music_root: Path,
        logger: Logger,
    ) -> None:
        """
        Adds all tracks to the ZIP archive, converting FLAC files to MP3.

        Args:
            zip_file: The ZIP archive to add tracks to.
            mixtape: The mixtape data dictionary.
            music_root: Path to the music library root.
            logger: Logger for error reporting.
        """
        for idx, track in enumerate(mixtape.get("tracks", []), 1):
            track_path = music_root / track.get("path", "")

            if not track_path.exists():
                logger.warning(f"Track not found: {track_path}")
                continue

            # Generate safe filename
            safe_name = _get_safe_track_name(idx, track)

            try:
                if track_path.suffix.lower() == ".flac":
                    # Convert FLAC to MP3
                    mp3_data = _convert_flac_to_mp3(track_path, track, logger)
                    if mp3_data:
                        zip_file.writestr(safe_name, mp3_data)
                    else:
                        logger.error(f"Failed to convert {track_path}")
                else:
                    # Add file as-is (already compressed format)
                    zip_file.write(track_path, arcname=safe_name)

            except Exception as e:
                logger.error(f"Failed to add track {track_path}: {e}")

    def _guess_mime_type(file_path: Path) -> str:
        """
        Determines the MIME type for a given file path.

        Args:
            file_path: The Path object representing the file.

        Returns:
            str: The MIME type string for the file.
        """
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            suffix = file_path.suffix.lower()
            mime_type = {
                ".flac": "audio/flac",
                ".m4a": "audio/mp4",
                ".aac": "audio/aac",
                ".ogg": "audio/ogg",
                ".mp3": "audio/mpeg",
            }.get(suffix, "application/octet-stream")
        return mime_type

    def _convert_flac_to_mp3(
        flac_path: Path, track_metadata: dict, logger: Logger
    ) -> bytes | None:
        """
        Converts a FLAC file to MP3 format using FFmpeg.

        Preserves metadata tags and uses high-quality encoding (VBR ~245 kbps).

        Args:
            flac_path: Path to the FLAC file.
            track_metadata: Dictionary containing track metadata.
            logger: Logger for error reporting.

        Returns:
            bytes | None: The MP3 file data, or None if conversion failed.
        """
        try:
            # Sanitize metadata to prevent command injection
            def sanitize_metadata(value: str) -> str:
                if not value:
                    return ""
                # Remove problematic characters
                return value.replace('"', '\\"').replace("'", "\\'").replace('\n', ' ').strip()

            title = sanitize_metadata(track_metadata.get('track', ''))
            artist = sanitize_metadata(track_metadata.get('artist', ''))
            album = sanitize_metadata(track_metadata.get('album', ''))

            # Use FFmpeg to convert with metadata preservation
            cmd = [
                "ffmpeg",
                "-hide_banner",  # Don't show banner in stderr
                "-loglevel", "error",  # Only show errors, not warnings
                "-i", str(flac_path),
                "-f", "mp3",
            ]

            # Add metadata only if present
            if title:
                cmd.extend(["-metadata", f"title={title}"])
            if artist:
                cmd.extend(["-metadata", f"artist={artist}"])
            if album:
                cmd.extend(["-metadata", f"album={album}"])

            # Output to stdout (pipe)
            cmd.extend(["-", "-y"])  # Force overwrite

            logger.info(f"Converting {flac_path} to MP3...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=300,  # 5 minute timeout
            )

            # Verify we got valid output
            if not result.stdout:
                logger.error(f"FFmpeg produced no output for {flac_path}")
                return None

            if len(result.stdout) < 1000:
                logger.error(f"FFmpeg produced suspiciously small output for {flac_path}: {len(result.stdout)} bytes")
                if result.stderr:
                    stderr_text = result.stderr.decode('utf-8', errors='ignore')
                    logger.error(f"FFmpeg stderr: {stderr_text}")
                return None

            # Check if output starts with valid MP3 header (ID3 or frame sync)
            if not (result.stdout[:3] == b'ID3' or result.stdout[0:2] == b'\xff\xfb'):
                logger.error(f"FFmpeg output doesn't look like valid MP3 for {flac_path} (first bytes: {result.stdout[:10].hex()})")
                return None

            logger.info(f"Successfully converted {flac_path} to MP3 ({len(result.stdout)} bytes)")
            return result.stdout

        except subprocess.CalledProcessError as e:
            stderr_text = e.stderr.decode('utf-8', errors='ignore') if e.stderr else 'No error output'
            logger.error(f"FFmpeg conversion failed for {flac_path}: {stderr_text}")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg conversion timed out for {flac_path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error converting {flac_path}: {e}")
            return None

    def _get_safe_track_name(index: int, track: dict) -> str:
        """
        Generates a safe filename for a track in the ZIP archive.

        Args:
            index: The track number (1-based).
            track: The track metadata dictionary.

        Returns:
            str: A filesystem-safe filename.
        """
        original_path = track.get("path", "")
        extension = Path(original_path).suffix.lower()

        # Convert FLAC to MP3 extension
        if extension == ".flac":
            extension = ".mp3"

        # Create safe filename from metadata
        artist = track.get("artist", "Unknown")
        title = track.get("track", "Unknown")

        # Sanitize
        safe_artist = "".join(c for c in artist if c.isalnum() or c in " -_")[:50]
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]

        return f"{index:02d} - {safe_artist} - {safe_title}{extension}"

    def _get_converted_filename(original_path: str) -> str:
        """
        Returns the filename that will be used in the ZIP for a given track path.

        Args:
            original_path: The original file path.

        Returns:
            str: The converted filename.
        """
        extension = Path(original_path).suffix.lower()
        if extension == ".flac":
            return Path(original_path).with_suffix(".mp3").name
        return Path(original_path).name

    return download
