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
        Generates an M3U playlist file for mobile music apps.
        
        This is the streaming option - tracks are fetched on-demand.
        Whether tracks are cached depends on the music app's behavior.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: An M3U playlist file with streaming URLs.
        """
        mode = request.args.get('mode', 'stream')  # 'stream', 'download', or 'auto'
        return _generate_m3u_playlist(slug, mode)

    @download.route("/<slug>/playlist-offline.m3u")
    def download_playlist_offline(slug: str) -> Response:
        """
        Generates an M3U playlist with local file references.
        
        This prompts the music app to download all tracks for offline use.
        The app will download each track and store it locally.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: An M3U playlist configured for offline use.
        """
        return _generate_m3u_playlist(slug, mode='download')

    def _generate_m3u_playlist(slug: str, mode: str = 'stream') -> Response:
        """
        Internal helper to generate M3U playlists with different caching strategies.
        
        Args:
            slug: The mixtape identifier.
            mode: 'stream' (default), 'download', or 'auto'
                - stream: URLs point to streaming endpoint
                - download: URLs use download disposition, prompting save
                - auto: Let the music app decide (same as stream but with cache hints)
        
        Returns:
            Response: An M3U playlist file.
        """
        mixtape = mixtape_manager.get(slug)
        if not mixtape:
            abort(404)

        # Create M3U playlist with direct URLs
        m3u_content = "#EXTM3U\n"
        m3u_content += f"#PLAYLIST:{mixtape.get('title', 'Mixtape')}\n\n"
        
        for track in mixtape.get("tracks", []):
            title = track.get("track", "Unknown")
            artist = track.get("artist", "Unknown")
            
            # Add metadata for the track
            m3u_content += f"#EXTINF:-1,{artist} - {title}\n"
            
            # Build URL based on mode
            if mode == 'download':
                # This URL will trigger a download prompt
                track_url = f"{request.url_root}download/{slug}/track-file/{track.get('path')}"
            else:
                # This URL is for streaming (but apps may cache)
                track_url = f"{request.url_root}download/{slug}/track/{track.get('path')}"
            
            m3u_content += f"{track_url}\n\n"
        
        filename = f"{slug}-offline.m3u" if mode == 'download' else f"{slug}.m3u"
        
        return Response(
            m3u_content,
            mimetype="audio/x-mpegurl",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
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
        # Read the offline player template from the static directory
        player_path = Path(__file__).parent / "templates" / "offline_player.html"
        
        if player_path.exists():
            with open(player_path, "r", encoding="utf-8") as f:
                player_html = f.read()
            zip_file.writestr("index.html", player_html)
        else:
            # Fallback: create a basic README if template is missing
            readme = """# Mixtape Offline Package

This package contains your mixtape for offline playback.

## Contents:
- mixtape.json: Metadata about your mixtape
- Audio files: All tracks in MP3 format
- cover.jpg/png: Cover artwork (if available)

To play:
1. Extract this ZIP file
2. Open the audio files in your preferred music player
3. Refer to mixtape.json for track order and information

Enjoy your music!
"""
            zip_file.writestr("README.txt", readme)

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

        Preserves metadata tags and uses high-quality encoding (320kbps).

        Args:
            flac_path: Path to the FLAC file.
            track_metadata: Dictionary containing track metadata.
            logger: Logger for error reporting.

        Returns:
            bytes | None: The MP3 file data, or None if conversion failed.
        """
        try:
            # Use FFmpeg to convert with metadata preservation
            cmd = [
                "ffmpeg",
                "-i", str(flac_path),
                "-codec:a", "libmp3lame",
                "-b:a", "320k",  # High quality
                "-metadata", f"title={track_metadata.get('track', '')}",
                "-metadata", f"artist={track_metadata.get('artist', '')}",
                "-metadata", f"album={track_metadata.get('album', '')}",
                "-f", "mp3",
                "-"  # Output to stdout
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=300,  # 5 minute timeout
            )
            
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed for {flac_path}: {e.stderr}")
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
