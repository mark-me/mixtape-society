from .authentication import create_authentication_blueprint
from .browse_mixtapes import create_browser_blueprint
from .editor import create_editor_blueprint
from .play import create_play_blueprint
from .download import create_download_blueprint

__all__ = [
    "create_authentication_blueprint",
    "create_browser_blueprint",
    "create_play_blueprint",
    "create_editor_blueprint",
    "create_download_blueprint"
]
