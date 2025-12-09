import json
import secrets
import shutil
from base64 import b64decode
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request

from auth import require_auth
from config import BaseConfig as Config
from logtools import get_logger
from musiclib import MusicCollection

logger = get_logger(__name__)



collection = MusicCollection(music_root=Config.MUSIC_ROOT, db_path=Config.DB_PATH)

editor = Blueprint(
    "editor", __name__, template_folder="templates", url_prefix="/editor"
)


@editor.route("/")
@require_auth
def new_mixtape() -> str:
    """
    Render de pagina voor het aanmaken van een nieuwe mixtape.

    Geeft het HTML-template terug voor het aanmaken van een nieuwe mixtape.

    Returns:
        str: De gerenderde HTML-pagina voor het aanmaken van een nieuwe mixtape.
    """
    return render_template("index.html")


@editor.route("/<slug>")
@require_auth
def edit_mixtape(slug: str) -> str:
    """
    Render de pagina voor het bewerken van een bestaande mixtape.

    Laadt de mixtape op basis van de slug en geeft het HTML-template terug met de vooringeladen mixtape-data. Geeft een 404 als de mixtape niet bestaat.

    Args:
        slug: De unieke slug van de mixtape.

    Returns:
        str: De gerenderde HTML-pagina voor het bewerken van de mixtape.
    """
    json_path = Config.MIXTAPE_DIR / f"{slug}.json"
    if not json_path.exists():
        abort(404)
    with open(json_path, "r", encoding="utf-8") as f:
        mixtape = json.load(f)
    return render_template("index.html", preload_mixtape=mixtape)


@editor.route("/search")
@require_auth
def search() -> object:
    """
    Voert een zoekopdracht uit in de muziekcollectie en geeft de resultaten terug als JSON.

    Zoekt naar artiesten, albums en tracks op basis van de query en highlight relevante matches. Geeft een lege lijst terug als de query te kort is.

    Returns:
        Response: Een JSON-response met de zoekresultaten.
    """
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    raw_results = collection.search_highlighting(query, limit=30)
    results = [_finalize_highlight(r) for r in raw_results]
    return jsonify(results)


def _finalize_highlight(item: dict) -> dict:
    """
    Finaliseert het highlighten van zoekresultaten.

    Kan uitgebreid worden om extra highlight-logica toe te voegen.

    Args:
        item: Het zoekresultaat-item als dictionary.

    Returns:
        dict: Het (mogelijk aangepaste) zoekresultaat-item.
    """
    return item


@editor.route("/save", methods=["POST"])
@require_auth
def save_mixtape() -> object:
    """
    Slaat een mixtape op basis van de ontvangen JSON-data op.

    Valideert de data, verwerkt de cover, vult metadata aan en slaat de mixtape op als JSON-bestand.
    Geeft een succesbericht of foutmelding als JSON-response terug.

    Returns:
        Response: Een JSON-response met succes of foutmelding.
    """
    try:
        data = request.get_json()
        if not data or not data.get("tracks"):
            return jsonify({"error": "Lege playlist"}), 400

        original_title = data.get("title", "Onbenoemde Playlist").strip() or "Onbenoemde Playlist"
        slug = _generate_slug(original_title)
        json_path = Config.MIXTAPE_DIR / f"{slug}.json"

        # Cover verwerken
        data["cover"] = _process_cover(data.get("cover"), slug)

        # Automatische fallback cover als er nog geen is
        if not data["cover"] and data["tracks"]:
            data["cover"] = _get_default_cover(data["tracks"][0]["path"], slug)

        # Metadata
        data["title"] = original_title
        data["slug"] = slug
        data["saved_at"] = datetime.now().isoformat()

        _save_mixtape_json(json_path, data)

        return jsonify({
            "success": True,
            "title": original_title,
            "slug": slug,
            "url": f"/editor/{slug}"
        })

    except Exception as e:
        logger.exception(f"Fout bij opslaan mixtape: {e}")
        return jsonify({"error": "Serverfout bij opslaan"}), 500


def _generate_slug(title: str) -> str:
    """
    Genereert een unieke slug voor een mixtape op basis van de titel.

    De slug bevat alleen veilige tekens, een datum en een random token.

    Args:
        title: De titel van de mixtape.

    Returns:
        str: De gegenereerde slug.
    """
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title.strip())
    safe = safe.strip("_- ") or "mixtape"
    token = secrets.token_urlsafe(8)
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{safe}_{timestamp}_{token}"


def _process_cover(cover_data: str, slug: str) -> str | None:
    """
    Verwerkt en slaat de cover-afbeelding op als deze aanwezig is.

    Decodeert de base64-afbeelding en slaat deze op als jpg-bestand. Geeft het pad naar de opgeslagen cover terug of None bij een fout.

    Args:
        cover_data: De base64-gecodeerde afbeelding als string.
        slug: De slug van de mixtape.

    Returns:
        str | None: Het relatieve pad naar de opgeslagen cover of None bij een fout.
    """
    if not cover_data or not cover_data.startswith("data:image"):
        return None
    try:
        header, b64data = cover_data.split(",", 1)
        img_data = b64decode(b64data)
        cover_path = Config.COVER_DIR / f"{slug}.jpg"
        with open(cover_path, "wb") as f:
            f.write(img_data)
        return f"covers/{slug}.jpg"
    except Exception as e:
        logger.error(f"Cover opslaan mislukt voor {slug}: {e}")
        return None


def _get_default_cover(track_path: str, slug: str) -> str | None:
    """
    Probeert een standaard cover-afbeelding te vinden in de album-map van het eerste nummer.

    Kopieert de gevonden afbeelding naar de covers-directory en retourneert het pad, of None als er geen cover gevonden is.

    Args:
        track_path: Het pad naar het eerste nummer van de mixtape.
        slug: De slug van de mixtape.

    Returns:
        str | None: Het relatieve pad naar de gevonden cover of None als er geen cover is.
    """
    full_track_path = Config.MUSIC_ROOT / track_path
    album_dir = full_track_path.parent
    possible = ["cover.jpg", "folder.jpg", "album.jpg", "front.jpg", "Cover.jpg", "Folder.jpg"]
    for name in possible:
        src = album_dir / name
        if src.exists():
            dest = Config.COVER_DIR / f"{slug}.jpg"
            shutil.copy(src, dest)
            return f"covers/{slug}.jpg"
    return None


def _save_mixtape_json(json_path: Path, data: dict) -> None:
    """
    Slaat de mixtape-data op als JSON-bestand.

    Schrijft de data naar het opgegeven pad in UTF-8 encoding.

    Args:
        json_path: Het pad waar het JSON-bestand opgeslagen moet worden.
        data: De mixtape-data als dictionary.

    Returns:
        None
    """
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

