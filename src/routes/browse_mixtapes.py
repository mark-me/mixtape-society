"""
Browse Mixtapes Blueprint - UPDATED for Multi-Collection Support

Handles browsing, searching, sorting, and managing mixtapes.
Now includes collection filtering and displays collection badges.
"""

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

from auth import check_auth, require_auth
from common.logging import Logger, NullLogger
from mixtape_manager import MixtapeManager


def create_browser_blueprint(
    mixtape_manager: MixtapeManager,
    func_processing_status: any,
    logger: Logger | None = None,
) -> Blueprint:
    """
    Creates and configures the Flask blueprint for browsing mixtapes.
    
    UPDATED: Now enriches mixtapes with collection information and
    supports filtering by collection.

    Args:
        mixtape_manager: The manager instance for retrieving and managing mixtapes
        func_processing_status: Function to check indexing/processing status
        logger: Logger instance for error reporting

    Returns:
        Configured Flask blueprint for browsing and managing mixtapes
    """
    browser = Blueprint("browse_mixtapes", __name__, template_folder="../templates")

    logger: Logger = logger or NullLogger()

    def _deep_search_mixtapes(mixtapes: list[dict], query: str) -> list[dict]:
        """
        Performs a deep search across mixtape tracks, artists, albums, and liner notes.
        
        Args:
            mixtapes: List of mixtape dictionaries to search
            query: Search query string (case-insensitive)
            
        Returns:
            Filtered list of mixtapes matching the search query
        """
        if not query:
            return mixtapes
            
        query_lower = query.lower()
        results = []
        
        for mixtape in mixtapes:
            # Search in mixtape title
            if query_lower in mixtape.get('title', '').lower():
                results.append(mixtape)
                continue
            
            # Search in liner notes
            if query_lower in mixtape.get('liner_notes', '').lower():
                results.append(mixtape)
                continue
                
            # Search within tracks
            tracks = mixtape.get('tracks', [])
            found = False
            for track in tracks:
                # Search track name
                if query_lower in track.get('track', '').lower():
                    found = True
                    break
                # Search artist
                if query_lower in track.get('artist', '').lower():
                    found = True
                    break
                # Search album
                if query_lower in track.get('album', '').lower():
                    found = True
                    break
                    
            if found:
                results.append(mixtape)
                
        return results

    @browser.route("/")
    @require_auth
    def browse() -> Response:
        """
        Renders the browse mixtapes page with collection support.
        
        UPDATED: Now enriches mixtapes with collection information and
        supports filtering by collection.

        Query Parameters:
            sort_by: Field to sort by (title, created_at, updated_at, track_count)
            sort_order: Sort direction (asc, desc)
            search: Search query string
            deep: Enable deep search (true/false)
            collection: Filter by collection ID (optional)

        Returns:
            Rendered template with mixtapes, collections, and filter state
        """
        from flask import request
        
        # Get query parameters
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')
        search_query = request.args.get('search', '').strip()
        search_deep = request.args.get('deep', '').lower() == 'true'
        collection_filter = request.args.get('collection')  # NEW
        
        # Get all mixtapes
        mixtapes = mixtape_manager.list_all()
        
        # ====================================================================
        # NEW: Enrich mixtapes with collection information
        # ====================================================================
        # Get collection_manager from mixtape_manager
        collection_manager = mixtape_manager.collection_manager
        
        # Check if we have CollectionManager (multi-collection mode)
        has_multiple_collections = hasattr(collection_manager, 'list_collections')
        
        if has_multiple_collections:
            # Get all collections for lookup
            collections = collection_manager.list_collections()
            collection_names = {c['id']: c['name'] for c in collections}
            
            # Enrich each mixtape with collection info
            for mixtape in mixtapes:
                collection_id = mixtape.get('collection_id')
                mixtape['collection_name'] = collection_names.get(
                    collection_id,
                    'Unknown'
                )
                mixtape['collection_id'] = collection_id or collection_manager._default_id
            
            # Count mixtapes per collection
            collection_counts = {}
            for mixtape in mixtapes:
                coll_id = mixtape.get('collection_id')
                collection_counts[coll_id] = collection_counts.get(coll_id, 0) + 1
            
            # Add counts to collections
            for coll in collections:
                coll['mixtape_count'] = collection_counts.get(coll['id'], 0)
        else:
            # Single collection mode - set default for all
            default_id = 'main'
            for mixtape in mixtapes:
                mixtape['collection_name'] = 'Main Collection'
                mixtape['collection_id'] = default_id
            
            collections = [{
                'id': default_id,
                'name': 'Main Collection',
                'mixtape_count': len(mixtapes),
                'is_default': True
            }]
        
        # ====================================================================
        # NEW: Filter by collection if specified
        # ====================================================================
        if collection_filter:
            mixtapes = [m for m in mixtapes if m.get('collection_id') == collection_filter]
        
        # Apply deep search if requested
        if search_query and search_deep:
            mixtapes = _deep_search_mixtapes(mixtapes, search_query)
        
        # Apply sorting
        if sort_by == 'title':
            mixtapes.sort(key=lambda x: x.get('title', '').lower(), 
                         reverse=(sort_order == 'desc'))
        elif sort_by == 'created_at':
            mixtapes.sort(key=lambda x: x.get('created_at') or '', 
                         reverse=(sort_order == 'desc'))
        elif sort_by == 'updated_at':
            mixtapes.sort(key=lambda x: x.get('updated_at') or x.get('created_at') or '', 
                         reverse=(sort_order == 'desc'))
        elif sort_by == 'track_count':
            mixtapes.sort(key=lambda x: len(x.get('tracks', [])), 
                         reverse=(sort_order == 'desc'))
        
        return render_template(
            "browse_mixtapes.html", 
            mixtapes=mixtapes,
            collections=collections,  # NEW
            has_multiple_collections=has_multiple_collections,  # NEW
            collection_filter=collection_filter,  # NEW
            sort_by=sort_by,
            sort_order=sort_order,
            search_query=search_query,
            search_deep=search_deep
        )

    @browser.route("/play/<slug>")
    @require_auth
    def play(slug: str) -> Response:
        """Redirects to the public play page for a given mixtape slug."""
        return redirect(url_for("public_play", slug=slug))

    @browser.route("/files/<path:filename>")
    @require_auth
    def files(filename: str) -> Response:
        """Serves a mixtape file from the mixtape directory."""
        return send_from_directory(current_app.config["MIXTAPE_DIR"], filename)

    @browser.route("/delete/<slug>", methods=["POST"])
    @require_auth
    def delete_mixtape(slug: str) -> Response:
        """Deletes a mixtape and its associated cover image."""
        try:
            # First check if it exists
            json_path = mixtape_manager.path_mixtapes / f"{slug}.json"
            if not json_path.exists():
                return jsonify({"success": False, "error": "Mixtape not found"}), 404

            mixtape_manager.delete(slug)
            return jsonify({"success": True}), 200

        except Exception as e:
            logger.exception("Error deleting mixtape")
            return jsonify({"success": False, "error": str(e)}), 500

    @browser.before_request
    def blueprint_require_auth() -> Response | None:
        """Ensures authentication for all routes in the browse_mixtapes blueprint."""
        if not check_auth():
            return redirect(url_for("landing"))

    return browser
