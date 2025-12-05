import datetime
import hashlib
import json
import mimetypes
import os
from io import BytesIO
from pathlib import Path

import mutagen
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Verander dit in productie!

# Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


# Hardcoded admin (voor demo; gebruik hashing in productie)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password"

# Directories
MIXTAPE_DIR = "mixtapes"
MUSIC_DIR = "/home/mark/Music"
COVER_DIR = "covers"
THUMBNAIL_CACHE = "thumbnail_cache"

os.makedirs(MIXTAPE_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_CACHE, exist_ok=True)


# Helper om mixtapes te laden
def load_mixtapes(sort_by="alpha"):
    """Loads all mixtapes from disk and sorts them by the specified criterion.

    This function reads all mixtape JSON files from the mixtape directory and returns a sorted list of mixtape metadata.

    Args:
        sort_by (str, optional): The sorting criterion ('alpha', 'created', or 'modified'). Defaults to "alpha".

    Returns:
        list: A list of dictionaries containing mixtape metadata.
    """
    mixtapes = []
    for filename in os.listdir(MIXTAPE_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(MIXTAPE_DIR, filename), "r") as f:
                data = json.load(f)
                data["filename"] = filename
                mixtapes.append(data)
    if sort_by == "alpha":
        mixtapes.sort(key=lambda x: x["title"].lower())
    elif sort_by == "created":
        mixtapes.sort(key=lambda x: x["created"], reverse=True)
    elif sort_by == "modified":
        mixtapes.sort(key=lambda x: x.get("modified", x["created"]), reverse=True)
    return mixtapes


def get_album_art(album_path: Path):
    """Retrieves album art for a given album directory.

    This function searches for common cover image files or extracts embedded art from the first audio file found.

    Args:
        album_path (Path): The path to the album directory.

    Returns:
        str or bytes or None: The path to the cover image, the image data, or None if no art is found.
    """
    covers = [
        "cover.jpg",
        "cover.png",
        "folder.jpg",
        "folder.png",
        "front.jpg",
        "albumart.jpg",
    ]
    for cover in covers:
        p = album_path / cover
        if p.exists():
            return str(p)

    # Try to extract from first audio file
    for audio_file in album_path.glob("*.*"):
        if audio_file.suffix.lower() in {".mp3", ".flac", ".m4a", ".ogg"}:
            try:
                audio = mutagen.File(audio_file)
                if hasattr(audio, "pictures") and audio.pictures:
                    return audio.pictures[0].data
                elif audio.get("APIC:"):
                    return audio["APIC:"].data
            except (AttributeError, KeyError, IndexError, TypeError):
                continue
    return None


@app.route("/")
def index():
    """Displays the main page with a list of mixtapes sorted by most recently modified.

    This endpoint renders the homepage, showing all mixtapes with the newest ones at the top.

    Returns:
        Response: The rendered index HTML page.
    """
    mixtapes = load_mixtapes(sort_by="modified")  # Nieuwste bovenaan
    return render_template("index.html", mixtapes=mixtapes)


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login and authentication.

    This endpoint verifies the provided username and password, logs in the user if credentials are correct, and redirects to the admin page. If authentication fails, it displays an error message.

    Returns:
        Response: Redirects to the admin page on success, or renders the login page with an error on failure.
    """
    error = None
    if request.method == "POST":
        if (
            request.form["username"] == ADMIN_USERNAME
            and request.form["password"] == ADMIN_PASSWORD
        ):
            user = User(1)
            login_user(user)
            return redirect(url_for("admin"))
        else:
            error = "Invalid username or password. Please try again."
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    """Logs out the current user and redirects to the login page.

    This endpoint ends the user's session and returns them to the login screen.

    Returns:
        Response: Redirects to the login page after logging out.
    """
    logout_user()
    return redirect(url_for("login"))


# Admin pagina
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    """Displays the admin page with a list of mixtapes.

    This endpoint renders the admin interface, showing all mixtapes sorted by the selected criterion.

    Returns:
        Response: The rendered admin HTML page.
    """
    sort_by = request.args.get("sort", "alpha")
    mixtapes = load_mixtapes(sort_by)
    return render_template("admin.html", mixtapes=mixtapes, sort_by=sort_by)


# Nieuwe mixtape aanmaken
@app.route("/create_mixtape", methods=["POST"])
@login_required
def create_mixtape():
    """Creates a new mixtape with the given title.

    This endpoint handles the creation of a new mixtape, initializing its metadata and saving it to disk.

    Returns:
        Response: Redirects to the admin page after creating the mixtape, or returns an error if the title is invalid or already exists.
    """
    title = request.form["title"]
    if not title:
        return "Titel vereist", 400
    filename = secure_filename(f"{title}.json")
    if os.path.exists(os.path.join(MIXTAPE_DIR, filename)):
        return "Titel bestaat al", 400

    data = {
        "title": title,
        "created": datetime.datetime.now().isoformat(),
        "modified": datetime.datetime.now().isoformat(),
        "tracks": [],  # Lijst van file paths
        "cover": None,  # Path naar cover art
    }
    with open(os.path.join(MIXTAPE_DIR, filename), "w") as f:
        json.dump(data, f)
    return redirect(url_for("admin"))


# Mixtape clonen
@app.route("/clone_mixtape/<title>", methods=["POST"])
@login_required
def clone_mixtape(title):
    """Creates a copy of an existing mixtape with a new title.

    This endpoint duplicates the specified mixtape, assigning it a new title and updated timestamps.

    Args:
        title (str): The title of the mixtape to clone.

    Returns:
        Response: Redirects to the admin page after cloning, or returns an error if the original mixtape is not found.
    """
    old_filename = secure_filename(f"{title}.json")
    old_path = os.path.join(MIXTAPE_DIR, old_filename)
    if not os.path.exists(old_path):
        return "Niet gevonden", 404

    with open(old_path, "r") as f:
        data = json.load(f)

    new_title = f"{title}_clone"
    new_filename = secure_filename(f"{new_title}.json")
    data["title"] = new_title
    data["created"] = datetime.datetime.now().isoformat()
    data["modified"] = datetime.datetime.now().isoformat()

    with open(os.path.join(MIXTAPE_DIR, new_filename), "w") as f:
        json.dump(data, f)
    return redirect(url_for("admin"))


# Mixtape verwijderen
@app.route("/delete_mixtape/<title>", methods=["POST"])
@login_required
def delete_mixtape(title):
    """Deletes the specified mixtape from the server.

    This endpoint removes the mixtape JSON file if it exists and redirects to the admin page.

    Args:
        title (str): The title of the mixtape to delete.

    Returns:
        Response: Redirects to the admin page after deletion.
    """
    filename = secure_filename(f"{title}.json")
    path = os.path.join(MIXTAPE_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("admin"))


@app.route("/edit/<title>", methods=["GET", "POST"])
@login_required
def edit_mixtape(title):
    """Edits the details and tracks of a specific mixtape.

    This endpoint allows updating the mixtape's title, adding or removing tracks, and changing the cover art.
    It handles both GET and POST requests for editing mixtape metadata and contents.

    Args:
        title (str): The title of the mixtape to edit.

    Returns:
        Response: Renders the edit page for GET requests, or redirects after processing POST actions.
    """
    filename = secure_filename(f"{title}.json")
    path = os.path.join(MIXTAPE_DIR, filename)

    if not os.path.exists(path):
        flash("Mixtape niet gevonden", "danger")
        return redirect(url_for("admin"))

    with open(path, "r") as f:
        data = json.load(f)

    available_tracks = _get_available_tracks()
    current_tracks = _get_current_tracks(data)

    if request.method == "POST":
        return _handle_edit_post_request(title, path, data)
    return render_template(
        "edit.html",
        mixtape=data,
        current_tracks=current_tracks,
        available_tracks=available_tracks,
    )


def _get_available_tracks():
    """Returns a list of available music tracks in the music directory.

    This function scans the music directory and returns all files with supported audio extensions.

    Returns:
        list: A list of filenames for available music tracks.
    """
    return [
        f
        for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith((".mp3", ".flac", ".ogg", ".oga"))
    ]


def _get_current_tracks(data):
    """Returns a list of current tracks with metadata for a mixtape.

    This function retrieves the tracks from the mixtape data and extracts their tags such as title, artist, and album.

    Args:
        data (dict): The mixtape data containing track paths.

    Returns:
        list: A list of dictionaries with track path, filename, and tags.
    """
    current_tracks = []
    for track_path in data.get("tracks", []):
        full_path = os.path.join(MUSIC_DIR, track_path.split("/")[-1])
        try:
            audio = mutagen.File(full_path)
            tags = {
                "title": str(audio.get("TIT2", [os.path.basename(track_path)])[0]),
                "artist": str(audio.get("TPE1", ["Onbekend"])[0]),
                "album": str(audio.get("TALB", [""])[0]),
            }
        except (mutagen.MutagenError, FileNotFoundError, AttributeError, TypeError):
            tags = {
                "title": os.path.basename(track_path),
                "artist": "Onbekend",
                "album": "",
            }
        current_tracks.append(
            {"path": track_path, "filename": os.path.basename(track_path), "tags": tags}
        )
    return current_tracks


def _handle_edit_post_request(title, path, data):
    """Handles POST requests for editing a mixtape.

    This function processes form and JSON requests to update the mixtape's title, add or remove tracks, or update the cover art.

    Args:
        title (str): The title of the mixtape being edited.
        path (str): The file path to the mixtape JSON.
        data (dict): The mixtape data.

    Returns:
        Response: A redirect or JSON response based on the action performed.
    """
    action = request.form.get("action")
    if request.content_type.is_json:
        data_json = request.get_json()
        if data_json.get("action") == "add_tracks":
            return _add_tracks_json(data_json, data, path)
    if action == "update_title":
        return _update_title(title, path, data)
    elif action == "add_tracks":
        return _add_tracks_form(data, path)
    elif action == "remove_track":
        return _remove_track(data, path)
    elif "cover" in request.files and request.files["cover"].filename:
        return _update_cover(title, data, path)
    return redirect(url_for("edit_mixtape", title=title))


def _add_tracks_json(data_json, data, path):
    """Adds tracks to a mixtape from a JSON request.

    This function processes a JSON payload to add new tracks to the mixtape and updates the mixtape file if any tracks are added.

    Args:
        data_json (dict): The JSON data containing the tracks to add.
        data (dict): The mixtape data to update.
        path (str): The file path to the mixtape JSON.

    Returns:
        Response: A JSON response indicating success and the number of tracks added.
    """
    tracks = data_json.get("tracks", [])
    added = 0
    for track in tracks:
        full_path = os.path.join(MUSIC_DIR, track.replace("/", os.sep))
        if os.path.exists(full_path) and full_path not in data["tracks"]:
            data["tracks"].append(full_path)
            added += 1
    if added:
        data["modified"] = datetime.datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify(success=True, added=added)
    return jsonify(success=False)


def _update_title(title, path, data):
    """Updates the title of a mixtape and handles renaming associated files.

    This function processes a form request to change the mixtape's title, renames the mixtape JSON and cover files if needed, and updates the mixtape metadata.

    Args:
        title (str): The current title of the mixtape.
        path (str): The file path to the current mixtape JSON.
        data (dict): The mixtape data to update.

    Returns:
        Response: Redirects to the edit page for the new or current title.
    """
    new_title = request.form["title"].strip()
    if not new_title:
        flash("Titel mag niet leeg zijn", "danger")
    elif new_title != title and os.path.exists(
        os.path.join(MIXTAPE_DIR, secure_filename(new_title + ".json"))
    ):
        flash("Er bestaat al een mixtape met deze titel", "danger")
    else:
        new_filename = secure_filename(new_title + ".json")
        os.rename(path, os.path.join(MIXTAPE_DIR, new_filename))
        if data.get("cover"):
            old_cover = data["cover"]
            new_cover = os.path.join(COVER_DIR, secure_filename(new_title + ".jpg"))
            if os.path.exists(old_cover):
                os.rename(old_cover, new_cover)
            data["cover"] = new_cover

        data["title"] = new_title
        data["modified"] = datetime.datetime.now().isoformat()
        with open(os.path.join(MIXTAPE_DIR, new_filename), "w") as f:
            json.dump(data, f, indent=2)
        flash("Titel bijgewerkt!", "success")
        return redirect(url_for("edit_mixtape", title=new_title))
    return redirect(url_for("edit_mixtape", title=title))


def _add_tracks_form(data, path):
    """Adds selected tracks to a mixtape from a form submission.

    This function processes a form request to add new tracks to the mixtape and updates the mixtape file if any tracks are added.

    Args:
        data (dict): The mixtape data to update.
        path (str): The file path to the mixtape JSON.

    Returns:
        Response: Redirects to the edit page for the mixtape after updating.
    """
    selected = request.form.getlist("new_tracks")
    added = 0
    for track in selected:
        track_path = os.path.join(MUSIC_DIR, track)
        if os.path.exists(track_path) and track_path not in data["tracks"]:
            data["tracks"].append(track_path)
            added += 1
    if added:
        data["modified"] = datetime.datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        flash(f"{added} track(s) toegevoegd", "success")
    else:
        flash("Geen nieuwe tracks geselecteerd", "info")
    return redirect(url_for("edit_mixtape", title=data["title"]))


def _remove_track(data, path):
    """Removes a track from a mixtape based on a form submission.

    This function processes a form request to remove a track from the mixtape and updates the mixtape file if the track is found.

    Args:
        data (dict): The mixtape data to update.
        path (str): The file path to the mixtape JSON.

    Returns:
        Response: Redirects to the edit page for the mixtape after updating.
    """
    track_to_remove = request.form["track_path"]
    if track_to_remove in data["tracks"]:
        data["tracks"].remove(track_to_remove)
        data["modified"] = datetime.datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        flash("Track verwijderd", "success")
    return redirect(url_for("edit_mixtape", title=data["title"]))


def _update_cover(title, data, path):
    """Updates the cover image for a mixtape from a form submission.

    This function processes a form request to upload and save a new cover image for the mixtape, updating the mixtape metadata accordingly.

    Args:
        title (str): The title of the mixtape.
        data (dict): The mixtape data to update.
        path (str): The file path to the mixtape JSON.

    Returns:
        Response: Redirects to the edit page for the mixtape after updating.
    """
    file = request.files["cover"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        flash("Alleen JPG/PNG/WebP toegestaan", "danger")
    else:
        cover_path = os.path.join(COVER_DIR, secure_filename(f"{title}.jpg"))
        file.save(cover_path)
        data["cover"] = cover_path
        data["modified"] = datetime.datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        flash("Cover bijgewerkt!", "success")
    return redirect(url_for("edit_mixtape", title=title))


# Tracks toevoegen aan mixtape (via form, selecteer uit MUSIC_DIR)
@app.route("/add_tracks/<title>", methods=["POST"])
@login_required
def add_tracks(title):
    """Adds selected tracks to a mixtape.

    This endpoint processes a form submission to add one or more tracks to the specified mixtape, ensuring only valid files are included.

    Args:
        title (str): The title of the mixtape to update.

    Returns:
        Response: Redirects to the admin page after updating the mixtape.
    """
    filename = secure_filename(f"{title}.json")
    path = os.path.join(MIXTAPE_DIR, filename)
    with open(path, "r") as f:
        data = json.load(f)

    selected_tracks = request.form.getlist("tracks")  # Meerdere selecties
    for track in selected_tracks:
        # Prevent directory traversal, but allow subdirectories
        track_path = os.path.normpath(os.path.join(MUSIC_DIR, track))
        if not track_path.startswith(os.path.abspath(MUSIC_DIR)):
            continue
        if os.path.exists(track_path) and track_path not in data["tracks"]:
            data["tracks"].append(track_path)

    data["modified"] = datetime.datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(data, f)
    return redirect(url_for("admin"))


@app.route("/album_thumb/<path:album_path>")
def album_thumb(album_path):
    """Returns a thumbnail image for the specified album directory.

    This endpoint generates and caches a small album art thumbnail for use in the UI, or returns a cached version if available.

    Args:
        album_path (str): The path to the album directory.

    Returns:
        Response: A JPEG image response containing the album thumbnail, or an empty response if no art is found.
    """
    album_dir = Path(MUSIC_DIR) / album_path.replace("|", "/")
    if not album_dir.is_dir():
        return "", 404

    cache_key = hashlib.md5(str(album_dir).encode()).hexdigest()
    cache_file = Path(THUMBNAIL_CACHE) / f"{cache_key}.jpg"

    # Serve from cache if exists and recent
    if (
        cache_file.exists()
        and (
            datetime.datetime.now()
            - datetime.datetime.fromtimestamp(cache_file.stat().st_mtime)
        ).days
        < 7
    ):
        return send_from_directory(THUMBNAIL_CACHE, cache_file.name)

    art = get_album_art(album_dir)
    if not art:
        return "", 204  # No art → transparent response

    if isinstance(art, (bytes, bytearray)):
        img_data = art
    else:
        img_data = Path(art).read_bytes()

    # Resize & cache
    img = Image.open(BytesIO(img_data))
    img.thumbnail((80, 80))
    output = BytesIO()
    img.save(output, format="JPEG", quality=85)
    img_bytes = output.getvalue()

    # Save to cache
    with open(cache_file, "wb") as f:
        f.write(img_bytes)

    return Response(img_bytes, mimetype="image/jpeg")


@app.route("/library_tree")
@login_required
def library_tree():
    """JSON voor jQuery File Tree (lazy loading via ?dir=param)."""
    root = Path(MUSIC_DIR)
    dir_param = request.args.get("dir", "").strip("/")
    current_path = root / dir_param if dir_param else root

    if not current_path.exists() or not current_path.is_dir():
        return jsonify({"directory": []})

    directory = []
    for item in sorted(current_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if item.is_file() and item.suffix.lower() in {".mp3", ".flac", ".ogg", ".oga", ".m4a"}:
            directory.append({"name": item.name, "type": "file"})
        elif item.is_dir():
            # Quick check voor lege dirs (optioneel)
            has_content = any(child.is_file() and child.suffix.lower() in {".mp3", ".flac", ".ogg", ".oga", ".m4a"}
                              for child in item.iterdir())
            if has_content or True:  # Toon alle dirs, lazy filtert leeg
                directory.append({"name": item.name, "type": "dir"})

    return jsonify({"directory": directory})

@app.route("/thumbnails/<filename>")
def thumbnails(filename):
    """Serves thumbnail image files from the thumbnail cache directory.

    This endpoint returns the requested thumbnail image file for use in the UI or music library explorer.

    Args:
        filename (str): The name of the thumbnail image file to serve.

    Returns:
        Response: The requested image file as a Flask response.
    """
    return send_from_directory(THUMBNAIL_CACHE, filename)

@app.route("/reorder_tracks/<title>", methods=["POST"])
@login_required
def reorder_tracks(title):
    """Reorders the tracks in a mixtape based on a new order provided in a POST request.

    This endpoint updates the track order in the specified mixtape, ensuring only existing tracks are included.

    Args:
        title (str): The title of the mixtape to reorder.

    Returns:
        Response: A JSON response indicating success or failure.
    """
    import json

    data = request.get_json()
    new_order = data.get("tracks", [])

    filename = secure_filename(f"{title}.json")
    path = os.path.join(MIXTAPE_DIR, filename)

    if not os.path.exists(path):
        return jsonify(success=False), 404

    with open(path, "r") as f:
        mixtape = json.load(f)

    # Behoud alleen tracks die nog bestaan
    valid_paths = [p for p in new_order if os.path.exists(p)]
    mixtape["tracks"] = valid_paths
    mixtape["modified"] = datetime.datetime.now().isoformat()

    with open(path, "w") as f:
        json.dump(mixtape, f, indent=2)

    return jsonify(success=True)


# Cover art uploaden
@app.route("/upload_cover/<title>", methods=["POST"])
@login_required
def upload_cover(title):
    """Uploads and updates the cover image for a mixtape.

    This endpoint processes a form submission to upload a new cover image for the specified mixtape and updates the mixtape metadata accordingly.

    Args:
        title (str): The title of the mixtape to update.

    Returns:
        Response: Redirects to the admin page after updating the cover image.
    """
    if "cover" not in request.files:
        return "Geen file", 400
    file = request.files["cover"]
    if file.filename == "":
        return "Geen file geselecteerd", 400

    filename = secure_filename(f"{title}.jpg")  # Bijv. JPG
    path = os.path.join(COVER_DIR, filename)
    file.save(path)

    json_filename = secure_filename(f"{title}.json")
    json_path = os.path.join(MIXTAPE_DIR, json_filename)
    with open(json_path, "r") as f:
        data = json.load(f)
    data["cover"] = path
    data["modified"] = datetime.datetime.now().isoformat()
    with open(json_path, "w") as f:
        json.dump(data, f)
    return redirect(url_for("admin"))


# Mixtape weergeven (publiek, deelbaar via link)
@app.route("/mixtape/<title>")
def mixtape(title):
    """Displays a public mixtape page with its playlist and metadata.

    This endpoint renders a shareable page for the specified mixtape, including track tags and a share link.

    Args:
        title (str): The title of the mixtape to display.

    Returns:
        Response: The rendered mixtape HTML page, or a 404 error if not found.
    """
    filename = secure_filename(f"{title}.json")
    path = os.path.join(MIXTAPE_DIR, filename)
    if not os.path.exists(path):
        return "Niet gevonden", 404

    with open(path, "r") as f:
        data = json.load(f)

    # Haal tags op voor playlist weergave
    playlist = []
    for track_path in data["tracks"]:
        try:
            audio = mutagen.File(track_path)
            tags = {
                "title": audio.get("TIT2", ["Unknown"])[0],
                "artist": audio.get("TPE1", ["Unknown"])[0],
                "album": audio.get("TALB", ["Unknown"])[0],
            }
        except:
            tags = {
                "title": os.path.basename(track_path),
                "artist": "Unknown",
                "album": "Unknown",
            }
        playlist.append({"path": track_path, "tags": tags})

    share_link = url_for("mixtape", title=title, _external=True)
    return render_template(
        "mixtape.html", data=data, playlist=playlist, share_link=share_link
    )


# Audio streamen
@app.route("/stream/<path:track_path>")
def stream(track_path):
    """Streams an audio track from the music directory to the client.

    This endpoint serves audio files in chunks, setting the appropriate MIME type for playback in browsers or media players.

    Args:
        track_path (str): The relative path to the audio track within the music directory.

    Returns:
        Response: A streaming response with the audio file, or a 404 error if the file is not found.
    """
    full_path = os.path.join(MUSIC_DIR, track_path)
    if not os.path.exists(full_path):
        return "Niet gevonden", 404

    def generate():
        with open(full_path, "rb") as f:
            while chunk := f.read(4096):
                yield chunk

    mimetypes.add_type("audio/mp4", ".m4a")
    mimetypes.add_type("audio/ogg", ".oga")
    mimetypes.add_type("audio/flac", ".flac")

    mimetype, _ = mimetypes.guess_type(track_path)
    if mimetype is None:
        # Fallback for unknown types
        ext = os.path.splitext(track_path)[1].lower()
        if ext == ".mp3":
            mimetype = "audio/mpeg"
        elif ext == ".flac":
            mimetype = "audio/flac"
        elif ext == ".ogg":
            mimetype = "audio/ogg"
        elif ext == ".m4a":
            mimetype = "audio/mp4"
        elif ext == ".oga":
            mimetype = "audio/ogg"
        else:
            mimetype = "application/octet-stream"
    return Response(generate(), mimetype=mimetype)


# Lijst van beschikbare tracks voor admin (om toe te voegen)
@app.route("/available_tracks")
@login_required
def available_tracks():
    """Returns a list of available audio tracks in the music directory for the admin interface.

    This endpoint scans the music directory and returns a JSON list of all supported audio files.

    Returns:
        Response: A JSON response containing the list of available tracks.
    """
    tracks = [
        f
        for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith((".mp3", ".flac", ".ogg"))
    ]
    return jsonify(tracks)


# Serve cover images
@app.route("/covers/<filename>")
def covers(filename):
    """Serves cover image files from the cover directory.

    This endpoint returns the requested cover image file for use in the UI or public mixtape pages.

    Args:
        filename (str): The name of the cover image file to serve.

    Returns:
        Response: The requested image file as a Flask response.
    """
    return send_from_directory(COVER_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
