# routes/collections.py

from flask import Blueprint, Response, jsonify
from auth import require_auth
from common.logging import Logger, NullLogger
from collection_manager import CollectionManager

def create_collections_blueprint(
    collection_manager: CollectionManager,
    logger: Logger | None = None
) -> Blueprint:
    """Blueprint for collection management API."""

    bp = Blueprint("collections_api", __name__)
    logger = logger or NullLogger()

    @bp.route("", methods=["GET"])
    @require_auth
    def list_collections() -> Response:
        """List all available collections with stats."""
        try:
            collections = collection_manager.list_collections()
            return jsonify(collections)
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return jsonify({"error": "Failed to list collections"}), 500

    @bp.route("/<collection_id>", methods=["GET"])
    @require_auth
    def get_collection_details(collection_id: str) -> Response:
        """Get detailed info about a specific collection."""
        try:
            info = collection_manager.get_info(collection_id)
            if not info:
                return jsonify({"error": "Collection not found"}), 404

            collection = collection_manager.get(collection_id)
            stats = collection.get_collection_stats() if collection else {}

            return jsonify({
                "id": info['id'],
                "name": info['name'],
                "description": info['description'],
                "stats": stats
            })
        except Exception as e:
            logger.error(f"Error getting collection {collection_id}: {e}")
            return jsonify({"error": str(e)}), 500

    return bp