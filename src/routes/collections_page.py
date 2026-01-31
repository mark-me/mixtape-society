"""
Collections Management Page Blueprint

Provides a web UI for managing collections with statistics.
"""

from flask import Blueprint, Response, render_template, request, jsonify
from pathlib import Path
from auth import require_auth
from common.logging import Logger, NullLogger
from collection_manager import CollectionManager
import yaml
import re


def create_collections_page_blueprint(
    collection_manager: CollectionManager,
    logger: Logger | None = None
) -> Blueprint:
    bp = Blueprint("collections_page", __name__)
    logger = logger or NullLogger()

    @bp.route("/")
    @require_auth
    def collections_page() -> str:
        """Render the collections management page with statistics."""
        try:
            # Get list of collections
            collections = collection_manager.list_collections()

            # Enrich each collection with stats
            for collection in collections:
                try:
                    # Get the actual collection object
                    coll = collection_manager.get(collection['id'])

                    if coll:
                        # Try to get full stats from collection
                        if hasattr(coll, 'get_collection_stats'):
                            stats = coll.get_collection_stats()
                            collection['stats'] = {
                                'num_tracks': stats.get('num_tracks', 0),
                                'num_artists': stats.get('num_artists', 0),
                                'num_albums': stats.get('num_albums', 0)
                            }
                        else:
                            # Fallback to individual count methods
                            collection['stats'] = {
                                'num_tracks': coll.get_track_count() if hasattr(coll, 'get_track_count') else 0,
                                'num_artists': coll.get_artist_count() if hasattr(coll, 'get_artist_count') else 0,
                                'num_albums': coll.get_album_count() if hasattr(coll, 'get_album_count') else 0
                            }
                    else:
                        # Collection not found, use zeros
                        collection['stats'] = {
                            'num_tracks': 0,
                            'num_artists': 0,
                            'num_albums': 0
                        }

                except Exception as e:
                    logger.error(f"Error loading stats for collection '{collection['id']}': {e}")
                    # Fallback to zeros on error
                    collection['stats'] = {
                        'num_tracks': 0,
                        'num_artists': 0,
                        'num_albums': 0
                    }

            return render_template("collections.html", collections=collections)

        except Exception as e:
            logger.error(f"Error loading collections page: {e}", exc_info=True)
            return f"<h1>Error: {e}</h1><a href='/mixtapes'>Back</a>", 500

    @bp.route("/add", methods=["POST"])
    @require_auth
    def add_collection() -> Response:
        try:
            data = request.get_json()

            # Validate
            if not data.get("id") or not data.get("name") or not data.get("music_root"):
                return jsonify({"error": "Missing required fields"}), 400

            if not re.match(r'^[a-zA-Z0-9_-]+$', data['id']):
                return jsonify({"error": "Invalid collection ID"}), 400

            # Check existence
            if any(c['id'] == data['id'] for c in collection_manager.list_collections()):
                return jsonify({"error": "Collection already exists"}), 400

            # Validate path
            if not Path(data['music_root']).is_dir():
                return jsonify({"error": "Music root path is not valid"}), 400

            # Auto-generate db_path if not provided
            if not data.get("db_path"):
                data["db_path"] = str(Path("collection-data") / f"{data['id']}.db")

            # Update config
            config_path = collection_manager._config_path
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}

            config.setdefault('collections', []).append({
                'id': data['id'],
                'name': data['name'],
                'description': data.get('description', ''),
                'music_root': data['music_root'],
                'db_path': data['db_path']
            })

            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

            collection_manager.reload_config()
            logger.info(f"Added collection: {data['id']}")

            return jsonify({"success": True, "collection_id": data['id']})
        except Exception as e:
            logger.error(f"Error adding collection: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @bp.route("/edit/<collection_id>", methods=["POST"])
    @require_auth
    def edit_collection(collection_id: str) -> Response:
        try:
            data = request.get_json()
            if not data.get("name"):
                return jsonify({"error": "Name is required"}), 400

            config_path = collection_manager._config_path
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}

            found = False
            for c in config.get('collections', []):
                if c['id'] == collection_id:
                    c['name'] = data['name']
                    c['description'] = data.get('description', '')
                    found = True
                    break

            if not found:
                return jsonify({"error": "Collection not found"}), 404

            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

            collection_manager.reload_config()
            logger.info(f"Updated collection: {collection_id}")

            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error editing collection: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @bp.route("/browse-path", methods=["GET"])
    @require_auth
    def browse_path() -> Response:
        """
        List immediate children of a directory for the path-picker UI.

        Query params:
            path  – absolute directory to list (defaults to "/")

        Returns JSON:
        {
            "current": "/music",
            "entries": [
                {"name": "Jazz",       "path": "/music/Jazz",       "is_dir": true},
                {"name": "cover.jpg",  "path": "/music/cover.jpg",  "is_dir": false}
            ]
        }

        Only directories are shown unless the caller passes ?show_files=1.
        Symlinks that resolve to directories are treated as directories.
        Permission errors on individual entries are silently skipped.
        """
        requested = request.args.get("path", "/").strip()
        show_files = request.args.get("show_files", "0") == "1"

        target = Path(requested).resolve()

        # Safety: must be an existing directory
        if not target.is_dir():
            return jsonify({"error": f"Not a directory: {requested}"}), 400

        entries: list[dict] = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    is_dir = child.is_dir()          # follows symlinks
                    if not is_dir and not show_files:
                        continue
                    entries.append({
                        "name":   child.name,
                        "path":   str(child),
                        "is_dir": is_dir
                    })
                except PermissionError:
                    continue                         # skip entries we can't stat
        except PermissionError:
            return jsonify({"error": f"Permission denied: {requested}"}), 403

        return jsonify({
            "current": str(target),
            "entries": entries
        })

    @bp.route("/delete/<collection_id>", methods=["POST"])
    @require_auth
    def delete_collection(collection_id: str) -> Response:
        try:
            collections = collection_manager.list_collections()
            if len(collections) <= 1:
                return jsonify({"error": "Cannot delete the only collection"}), 400

            if collection_id == collection_manager._default_id:
                return jsonify({"error": "Cannot delete the default collection"}), 400

            config_path = collection_manager._config_path
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}

            config['collections'] = [c for c in config.get('collections', []) if c['id'] != collection_id]

            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

            collection_manager.reload_config()
            logger.info(f"Deleted collection: {collection_id}")

            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error deleting collection: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    return bp
