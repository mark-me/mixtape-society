"""
Collections API Blueprint

Provides REST API endpoints for managing and querying collections.
"""

from flask import Blueprint, Response, jsonify, request
from auth import require_auth
from common.logging import Logger, NullLogger
from collection_manager import CollectionManager, CollectionNotFoundError


def create_collections_blueprint(
    collection_manager: CollectionManager,
    logger: Logger | None = None
) -> Blueprint:
    """
    Creates the collections API blueprint.
    
    Provides endpoints for:
    - Listing all collections
    - Getting collection details
    - Triggering collection resyncs
    - Getting collection statistics
    
    Args:
        collection_manager: CollectionManager instance
        logger: Logger instance for error reporting
    
    Returns:
        Configured Blueprint for collections API
    """
    
    bp = Blueprint("collections_api", __name__)
    logger = logger or NullLogger()
    
    @bp.route("", methods=["GET"])
    @require_auth
    def list_collections() -> Response:
        """
        List all available collections with statistics.
        
        Returns:
            JSON array of collection objects with:
            - id: Collection unique identifier
            - name: Display name
            - description: Description
            - music_root: Path to music files
            - db_path: Path to database
            - is_default: Whether this is the default collection
            - stats: Statistics (track_count, artist_count, album_count)
        
        Example:
            GET /api/collections
            
            Response:
            [
                {
                    "id": "main",
                    "name": "Main Collection",
                    "description": "Primary music library",
                    "music_root": "/music",
                    "db_path": "/data/main.db",
                    "is_default": true,
                    "stats": {
                        "track_count": 5420,
                        "artist_count": 342,
                        "album_count": 512
                    }
                },
                {
                    "id": "jazz",
                    "name": "Jazz Archive",
                    "description": "Complete jazz collection",
                    "music_root": "/music/jazz",
                    "db_path": "/data/jazz.db",
                    "is_default": false,
                    "stats": {
                        "track_count": 2103,
                        "artist_count": 89,
                        "album_count": 201
                    }
                }
            ]
        """
        try:
            collections = collection_manager.list_collections()
            return jsonify(collections)
        except Exception as e:
            logger.error(f"Error listing collections: {e}", exc_info=True)
            return jsonify({"error": "Failed to list collections"}), 500
    
    @bp.route("/<collection_id>", methods=["GET"])
    @require_auth
    def get_collection_details(collection_id: str) -> Response:
        """
        Get detailed information about a specific collection.
        
        Args:
            collection_id: Collection unique identifier
        
        Returns:
            JSON object with collection details and statistics
        
        Example:
            GET /api/collections/jazz
            
            Response:
            {
                "id": "jazz",
                "name": "Jazz Archive",
                "description": "Complete jazz collection",
                "music_root": "/music/jazz",
                "db_path": "/data/jazz.db",
                "is_default": false,
                "stats": {
                    "track_count": 2103,
                    "artist_count": 89,
                    "album_count": 201,
                    "total_duration": 567890,
                    "total_size": 15234567890
                }
            }
        """
        try:
            info = collection_manager.get_info(collection_id)
            if not info:
                return jsonify({"error": "Collection not found"}), 404
            
            # Get statistics
            collection = collection_manager.get(collection_id)
            if collection:
                try:
                    stats = collection.get_collection_stats()
                except Exception as e:
                    logger.error(f"Error getting stats for {collection_id}: {e}")
                    stats = {"error": "Failed to retrieve statistics"}
            else:
                stats = {}
            
            return jsonify({
                "id": info['id'],
                "name": info['name'],
                "description": info['description'],
                "music_root": info['music_root'],
                "db_path": info['db_path'],
                "is_default": info['is_default'],
                "stats": stats
            })
            
        except Exception as e:
            logger.error(f"Error getting collection {collection_id}: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    
    @bp.route("/<collection_id>/resync", methods=["POST"])
    @require_auth
    def resync_collection(collection_id: str) -> Response:
        """
        Trigger a resync for a specific collection.
        
        Resyncing scans the music_root directory and updates the database
        to match the current file system state (adding new files, removing
        deleted files, updating modified files).
        
        Args:
            collection_id: Collection unique identifier
        
        Returns:
            JSON with success status and message
        
        Example:
            POST /api/collections/jazz/resync
            
            Response:
            {
                "success": true,
                "message": "Resync started for collection 'jazz'",
                "collection_id": "jazz"
            }
        """
        try:
            collection = collection_manager.get(collection_id)
            if not collection:
                return jsonify({"error": "Collection not found"}), 404
            
            # Run resync in background thread
            import threading
            
            def run_resync():
                try:
                    logger.info(f"Starting resync for collection '{collection_id}'")
                    collection.resync()
                    logger.info(f"Resync completed for collection '{collection_id}'")
                except Exception as e:
                    logger.exception(f"Resync error for collection '{collection_id}': {e}")
            
            thread = threading.Thread(target=run_resync, daemon=True)
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"Resync started for collection '{collection_id}'",
                "collection_id": collection_id
            })
        
        except Exception as e:
            logger.error(f"Error initiating resync for {collection_id}: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    
    @bp.route("/<collection_id>/stats", methods=["GET"])
    @require_auth
    def get_collection_stats(collection_id: str) -> Response:
        """
        Get statistics for a specific collection.
        
        Args:
            collection_id: Collection unique identifier
        
        Returns:
            JSON object with collection statistics
        
        Example:
            GET /api/collections/jazz/stats
            
            Response:
            {
                "track_count": 2103,
                "artist_count": 89,
                "album_count": 201,
                "total_duration": 567890,
                "total_size": 15234567890,
                "genres": ["Jazz", "Blues", "Bebop"]
            }
        """
        try:
            collection = collection_manager.get(collection_id)
            if not collection:
                return jsonify({"error": "Collection not found"}), 404
            
            stats = collection.get_collection_stats()
            return jsonify(stats)
            
        except Exception as e:
            logger.error(f"Error getting stats for {collection_id}: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    
    @bp.route("/reload", methods=["POST"])
    @require_auth
    def reload_collections() -> Response:
        """
        Reload collections.yml configuration without restarting the app.
        
        WARNING: This closes all existing collections and recreates them.
        Any references to old collection objects will become invalid.
        
        Use this endpoint after editing collections.yml to apply changes
        without restarting the entire application.
        
        Returns:
            JSON with success status and list of reloaded collections
        
        Example:
            POST /api/collections/reload
            
            Response:
            {
                "success": true,
                "message": "Collections reloaded successfully",
                "collections": [
                    {"id": "main", "name": "Main Collection"},
                    {"id": "jazz", "name": "Jazz Archive"}
                ]
            }
        """
        try:
            logger.info("Reloading collections configuration")
            collection_manager.reload_config()
            
            # Get updated collection list
            collections = [
                {"id": c['id'], "name": c['name']}
                for c in collection_manager.list_collections()
            ]
            
            logger.info(f"Collections reloaded: {len(collections)} collection(s)")
            
            return jsonify({
                "success": True,
                "message": "Collections reloaded successfully",
                "collections": collections
            })
            
        except Exception as e:
            logger.error(f"Error reloading collections: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    return bp
