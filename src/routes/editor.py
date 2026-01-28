"""
Editor Blueprint - UPDATED for Multi-Collection Support

Handles mixtape creation, editing, searching, and saving.
Now supports selecting collections and searching within specific collections.
"""

import threading
import time
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from audio_cache import (
    ProgressCallback,
    ProgressStatus,
    get_progress_tracker,
    schedule_mixtape_caching,
)
from auth import require_auth
from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager
from preferences import PreferencesManager
from utils import CoverCompositor


def create_editor_blueprint(
    collection_manager,  # CHANGED: was 'collection: MusicCollectionUI'
    logger: Logger | None = None
) -> Blueprint:
    """
    Creates and configures the Flask blueprint for the mixtape editor.
    
    UPDATED: Now accepts collection_manager instead of single collection.
    Supports searching within specific collections and stores collection_id
    in mixtape metadata.

    Args:
        collection_manager: CollectionManager instance (or MusicCollectionUI for backward compat)
        logger: Logger instance for error reporting

    Returns:
        Configured Flask blueprint for the editor
    """
    editor = Blueprint("editor", __name__)
    logger = logger or NullLogger()
    
    # ========================================================================
    # Detect if we have CollectionManager or single collection
    # ========================================================================
    has_collection_manager = hasattr(collection_manager, 'list_collections')
    
    if has_collection_manager:
        logger.info("Editor initialized with CollectionManager (multi-collection mode)")
        default_collection = collection_manager.get_default()
    else:
        logger.info("Editor initialized with single collection (backward compatible mode)")
        default_collection = collection_manager
    
    # Initialize preferences manager
    def get_preferences_manager():
        """Get PreferencesManager instance using current app config."""
        return PreferencesManager(
            data_root=current_app.config["DATA_ROOT"], logger=logger
        )

    @editor.route("/preferences", methods=["GET"])
    @require_auth
    def get_preferences() -> Response:
        """Get user preferences including creator name and default settings."""
        try:
            prefs_manager = get_preferences_manager()
            preferences = prefs_manager.get_preferences()
            return jsonify(preferences)
        except Exception as e:
            logger.error(f"Error fetching preferences: {e}")
            return jsonify({"error": str(e)}), 500

    @editor.route("/preferences", methods=["POST"])
    @require_auth
    def update_preferences() -> Response:
        """
        Update user preferences.
        
        Accepts JSON with any of:
        - creator_name
        - default_gift_flow_enabled
        - default_show_tracklist
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            prefs_manager = get_preferences_manager()
            updated_prefs = prefs_manager.update_preferences(data)

            return jsonify({"success": True, "preferences": updated_prefs})
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return jsonify({"error": str(e)}), 500

    # ========================================================================
    # NEW: Collections endpoint for UI
    # ========================================================================
    @editor.route("/collections", methods=["GET"])
    @require_auth
    def get_collections() -> Response:
        """
        Get list of available collections for the collection selector UI.
        
        Returns:
            JSON array of collections with id, name, description, and stats
        
        Example response:
            {
                "collections": [
                    {
                        "id": "main",
                        "name": "Main Collection",
                        "description": "Primary music library",
                        "stats": {"track_count": 5420, "artist_count": 342}
                    },
                    {
                        "id": "jazz",
                        "name": "Jazz Archive",
                        "description": "Complete jazz collection",
                        "stats": {"track_count": 2103, "artist_count": 89}
                    }
                ],
                "default_collection": "main",
                "has_multiple": true
            }
        """
        try:
            if has_collection_manager:
                collections = collection_manager.list_collections()
                default_id = collection_manager._default_id
                
                return jsonify({
                    "collections": collections,
                    "default_collection": default_id,
                    "has_multiple": len(collections) > 1
                })
            else:
                # Single collection mode - return minimal info
                return jsonify({
                    "collections": [{
                        "id": "main",
                        "name": "Main Collection",
                        "description": "Primary music library",
                        "stats": default_collection.get_collection_stats()
                    }],
                    "default_collection": "main",
                    "has_multiple": False
                })
        except Exception as e:
            logger.error(f"Error getting collections: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @editor.route("/")
    @require_auth
    def new_mixtape() -> str:
        """
        Render the page for creating a new mixtape.
        
        UPDATED: Now passes collection information to template.
        """
        # Get user preferences for defaults
        prefs_manager = get_preferences_manager()
        preferences = prefs_manager.get_preferences()

        empty_mixtape = {
            "title": "",
            "cover": None,
            "liner_notes": "",
            "tracks": [],
            "slug": None,
            "created_at": None,
            "updated_at": None,
            "collection_id": None,  # NEW: Will be set when user selects collection
            "creator_name": preferences.get("creator_name", ""),
            "gift_flow_enabled": preferences.get("default_gift_flow_enabled", False),
            "unwrap_style": "playful",
            "show_tracklist_after_completion": preferences.get(
                "default_show_tracklist", True
            ),
        }
        
        # Pass collection info to template
        if has_collection_manager:
            collections = collection_manager.list_collections()
            default_collection_id = collection_manager._default_id
        else:
            collections = [{"id": "main", "name": "Main Collection"}]
            default_collection_id = "main"
        
        return render_template(
            "editor.html",
            preload_mixtape=empty_mixtape,
            collections=collections,
            default_collection=default_collection_id,
            has_multiple_collections=has_collection_manager and len(collections) > 1
        )

    @editor.route("/<slug>")
    @require_auth
    def edit_mixtape(slug: str) -> str:
        """
        Loads and renders the page for editing an existing mixtape.
        
        UPDATED: Now passes collection information and locks to the mixtape's collection.
        """
        mixtape_manager = MixtapeManager(
            path_mixtapes=current_app.config["MIXTAPE_DIR"],
            collection_manager=collection_manager  # CHANGED: was collection=collection
        )
        mixtape = mixtape_manager.get(slug)
        
        # Get collection info
        if has_collection_manager:
            collections = collection_manager.list_collections()
            mixtape_collection_id = mixtape.get('collection_id') or collection_manager._default_id
        else:
            collections = [{"id": "main", "name": "Main Collection"}]
            mixtape_collection_id = "main"
        
        return render_template(
            "editor.html",
            preload_mixtape=mixtape,
            editing_slug=slug,
            collections=collections,
            default_collection=mixtape_collection_id,
            has_multiple_collections=has_collection_manager and len(collections) > 1,
            editing_mode=True  # NEW: Indicates collection should be locked
        )

    # ========================================================================
    # UPDATED: Search endpoint with collection support
    # ========================================================================
    @editor.route("/search")
    @require_auth
    def search() -> Response:
        """
        Searches the music collection and returns the results.
        
        UPDATED: Now accepts optional collection_id parameter to search
        within a specific collection.
        
        Query Parameters:
            q: Search query (required, min 2 characters)
            collection_id: Collection to search (optional, defaults to default collection)
        
        Returns:
            JSON array of search results with highlighted matches
        """
        try:
            query = request.args.get("q", "").strip()
            if len(query) < 2:
                return jsonify([])
            
            # NEW: Get collection_id parameter
            collection_id = request.args.get("collection_id")
            
            # Get appropriate collection
            if has_collection_manager and collection_id:
                # Multi-collection mode with specific collection
                collection = collection_manager.get(collection_id)
                if not collection:
                    logger.error(f"Collection '{collection_id}' not found")
                    return jsonify({
                        "error": "Collection not found",
                        "collection_id": collection_id
                    }), 404
                logger.debug(f"Searching collection '{collection_id}' for: {query}")
            else:
                # Single collection mode or no specific collection
                collection = default_collection
                logger.debug(f"Searching default collection for: {query}")
            
            # Perform search
            results = collection.search_highlighting(query, limit=50)
            
            # NEW: Add collection_id to each result for UI display
            if has_collection_manager and collection_id:
                for result in results:
                    result['collection_id'] = collection_id
            
            return jsonify(results)

        except Exception as e:
            logger.error(f"Search error for query '{query}': {e}", exc_info=True)
            return jsonify({
                "error": "Search failed",
                "message": str(e),
                "query": query
            }), 500

    # ========================================================================
    # UPDATED: Artist and Album details with collection support
    # ========================================================================
    @editor.route("/artist_details")
    @require_auth
    def artist_details() -> Response:
        """
        Get detailed information about an artist.
        
        UPDATED: Now accepts optional collection_id parameter.
        
        Query Parameters:
            artist: Artist name (required)
            collection_id: Collection to query (optional)
        """
        try:
            artist = request.args.get("artist", "").strip()
            if not artist:
                return jsonify({"error": "Missing artist"}), 400
            
            collection_id = request.args.get("collection_id")
            
            # Get appropriate collection
            if has_collection_manager and collection_id:
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({"error": "Collection not found"}), 404
            else:
                collection = default_collection
            
            details = collection.get_artist_details(artist)
            return jsonify(details)
            
        except Exception as e:
            logger.error(f"Error getting artist details: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @editor.route("/album_details")
    @require_auth
    def album_details() -> Response:
        """
        Get detailed information about an album.
        
        UPDATED: Now accepts optional collection_id parameter.
        
        Query Parameters:
            release_dir: Release directory (required)
            collection_id: Collection to query (optional)
        """
        try:
            release_dir = request.args.get("release_dir", "").strip()
            if not release_dir:
                return jsonify({"error": "Missing release_dir"}), 400
            
            collection_id = request.args.get("collection_id")
            
            # Get appropriate collection
            if has_collection_manager and collection_id:
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({"error": "Collection not found"}), 404
            else:
                collection = default_collection
            
            details = collection.get_album_details(release_dir)
            return jsonify(details)
            
        except Exception as e:
            logger.error(f"Error getting album details: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    # ========================================================================
    # UPDATED: Save endpoint stores collection_id
    # ========================================================================
    @editor.route("/save", methods=["POST"])
    @require_auth
    def save_mixtape() -> Response:
        """
        Saves a new or edited mixtape.
        
        UPDATED: Now stores collection_id in mixtape metadata.
        
        Request body must include:
            - title: Mixtape title
            - tracks: Array of track objects
            - collection_id: Collection these tracks are from (NEW)
            - Other metadata fields...
        """
        try:
            data = request.get_json()
            if not data or not data.get("tracks"):
                return jsonify({"error": "Empty mixtape"}), 400

            title = data.get("title", "").strip() or "Unnamed Mixtape"
            liner_notes = data.get("liner_notes", "")
            slug = data.get("slug")  # Present only when editing
            
            # NEW: Get collection_id
            collection_id = data.get("collection_id")
            if not collection_id:
                # If not provided, use default
                if has_collection_manager:
                    collection_id = collection_manager._default_id
                else:
                    collection_id = "main"
                logger.warning(f"No collection_id provided, using default: {collection_id}")

            # Get gift flow fields
            creator_name = data.get("creator_name", "").strip()
            unwrap_style = data.get("unwrap_style", "playful")
            gift_flow_enabled = data.get("gift_flow_enabled", False)
            show_tracklist_after_completion = data.get(
                "show_tracklist_after_completion", True
            )

            # Validate fields
            valid_unwrap_styles = ["playful", "elegant"]
            if unwrap_style not in valid_unwrap_styles:
                return jsonify({
                    "error": f"Invalid unwrap_style. Must be one of: {', '.join(valid_unwrap_styles)}"
                }), 400

            if not isinstance(gift_flow_enabled, bool):
                return jsonify({"error": "gift_flow_enabled must be a boolean"}), 400

            if not isinstance(show_tracklist_after_completion, bool):
                return jsonify({"error": "show_tracklist_after_completion must be a boolean"}), 400

            if len(creator_name) > 100:
                return jsonify({"error": "creator_name must be 100 characters or less"}), 400

            if len(title) > 200:
                return jsonify({"error": "title must be 200 characters or less"}), 400

            # Get the collection to fetch covers
            if has_collection_manager:
                collection = collection_manager.get(collection_id)
                if not collection:
                    return jsonify({
                        "error": f"Collection '{collection_id}' not found"
                    }), 404
            else:
                collection = default_collection

            # Add track covers
            tracks = data.get("tracks", [])
            for track in tracks:
                release_dir = collection._get_release_dir(track.get("path", ""))
                track["cover"] = collection.get_cover(release_dir)

            # Prepare mixtape data
            mixtape_data = {
                "title": title,
                "tracks": tracks,
                "liner_notes": liner_notes,
                "cover": data.get("cover"),
                "collection_id": collection_id,  # NEW: Store collection ID
                "creator_name": creator_name,
                "gift_flow_enabled": gift_flow_enabled,
                "unwrap_style": unwrap_style,
                "show_tracklist_after_completion": show_tracklist_after_completion,
            }

            # Instantiate the manager
            mixtape_manager = MixtapeManager(
                path_mixtapes=current_app.config["MIXTAPE_DIR"],
                collection_manager=collection_manager  # CHANGED
            )

            # Handle cover image if provided
            cover_data = data.get("cover")
            if cover_data and cover_data.startswith("data:image"):
                # Extract base64 data
                import base64
                import re
                
                match = re.match(r'data:image/(\w+);base64,(.+)', cover_data)
                if match:
                    image_format = match.group(1)
                    image_data = match.group(2)
                    
                    # Decode base64
                    try:
                        image_bytes = base64.b64decode(image_data)
                        mixtape_data["cover_data"] = image_bytes
                        mixtape_data["cover_format"] = image_format
                    except Exception as e:
                        logger.error(f"Error decoding cover image: {e}")

            # Save or update
            if slug:
                # Editing existing mixtape
                result_slug = mixtape_manager.update(slug, mixtape_data)
                message = "Mixtape updated successfully"
            else:
                # Creating new mixtape
                result_slug = mixtape_manager.create(mixtape_data)
                message = "Mixtape created successfully"

            return jsonify({
                "success": True,
                "slug": result_slug,
                "message": message,
                "collection_id": collection_id  # NEW: Return collection ID
            })

        except Exception as e:
            logger.error(f"Error saving mixtape: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    # Additional routes (cover generation, caching, etc.) would continue here
    # For brevity, I'm including just the key changed endpoints
    # The rest of the routes remain largely unchanged

    return editor
