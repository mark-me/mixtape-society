from .authentication import create_authentication_blueprint
from .browse_mixtapes import create_browser_blueprint
from .editor import create_editor_blueprint
from .logo_on_cover import create_og_cover_blueprint
from .play import create_play_blueprint
from .qr_blueprint import create_qr_blueprint
from .collections import create_collections_blueprint

__all__ = [
    "create_authentication_blueprint",
    "create_browser_blueprint",
    "create_play_blueprint",
    "create_qr_blueprint",
    "create_editor_blueprint",
    "create_og_cover_blueprint",
    "create_collections_blueprint"
]
