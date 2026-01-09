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
    Creates and configures the Flask blueprint for browsing, playing, and managing mixtapes.

    Sets up routes for listing mixtapes, serving cover images and files, deleting mixtapes, and handling authentication for all routes in the blueprint.

    Args:
        mixtape_manager (MixtapeManager): The manager instance for retrieving and managing mixtapes.
        func_processing_status (any): A function to check the current indexing or processing status.
        logger (Logger): The logger instance for error reporting.

    Returns:
        Blueprint: The configured Flask blueprint for browsing and managing mixtapes.
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
        Renders the browse mixtapes page or indexing progress if active.

        Checks for ongoing indexing and shows progress if active. Otherwise, lists all mixtapes.
        Supports sorting by title, date (created/updated), and track count with ascending/descending order.
        Supports search by title (client-side) and deep search by tracks/artists/albums (server-side).

        Returns:
            Response: The rendered template for mixtapes or indexing progress.
        """
        from flask import request
        
        # Get sorting parameters from query string
        sort_by = request.args.get('sort_by', 'updated_at')  # default: most recent
        sort_order = request.args.get('sort_order', 'desc')  # default: descending
        search_query = request.args.get('search', '').strip()
        search_deep = request.args.get('deep', '').lower() == 'true'
        
        mixtapes = mixtape_manager.list_all()
        
        # Apply deep search if requested (searches within tracks, artists, albums)
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
        
        return render_template("browse_mixtapes.html", 
                             mixtapes=mixtapes,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             search_query=search_query,
                             search_deep=search_deep)

    @browser.route("/play/<slug>")
    @require_auth
    def play(slug: str) -> Response:
        """
        Redirects to the public play page for a given mixtape slug.

        Takes the mixtape slug and redirects the user to the corresponding public play route.

        Args:
            slug: The unique identifier for the mixtape.

        Returns:
            Response: A redirect response to the public play page for the mixtape.
        """
        return redirect(url_for("public_play", slug=slug))

    @browser.route("/files/<path:filename>")
    @require_auth
    def files(filename: str) -> Response:
        """
        Serves a mixtape file from the mixtape directory.

        Returns the requested file as a Flask response for download or display.

        Args:
            filename: The path to the mixtape file within the mixtape directory.

        Returns:
            Response: A Flask response serving the requested file.
        """
        return send_from_directory(current_app.config["MIXTAPE_DIR"], filename)

    @browser.route("/delete/<slug>", methods=["POST"])
    @require_auth
    def delete_mixtape(slug: str) -> Response:
        """
        Deletes a mixtape and its associated cover image.

        Removes the mixtape JSON file and cover image from disk if they exist. Returns a 200 response on success or 404 if the mixtape is not found.

        Args:
            slug: The unique identifier for the mixtape to delete.

        Returns:
            Response: An empty response with status 200 if successful, or 404 if the mixtape does not exist.
        """
        try:
            # First check if it exists
            json_path = mixtape_manager.path_mixtapes / f"{slug}.json"
            if not json_path.exists():
                return jsonify({"success": False, "error": "Mixtape not found"}), 404

            mixtape_manager.delete(slug)
            return jsonify({"success": True}), 200

        except Exception as e:
            logger.exception("Error deleting mixtape")  # if you have logger
            return jsonify({"success": False, "error": str(e)}), 500

    @browser.before_request
    def blueprint_require_auth() -> Response | None:
        """
        Ensures authentication for all routes in the browse_mixtapes blueprint.

        Checks if the user is authenticated before allowing access to any route in this blueprint. Redirects unauthenticated users to the landing page.

        Returns:
            Response or None: A redirect response to the landing page if not authenticated, otherwise None.
        """
        # Protect everything in this blueprint
        if not check_auth():
            return redirect(url_for("landing"))

    return browser
