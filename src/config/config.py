# src/config/config.py
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env from project root only in development (not in Docker)
if os.getenv("APP_ENV", "development") != "production":
    project_root = Path(__file__).parent.parent.parent  # src/config → project root
    load_dotenv(project_root / ".env")

BASE_DIR = Path(__file__).parent.parent  # src/

class BaseConfig:
    """Base configuration shared by all application environments.

    This configuration defines paths, credentials, and caching settings that
    control how the app accesses music, stores data, and manages audio cache.
    """
    # 1. Music library location
    MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/music"))

    # 2. NEW: Single data root for everything the app writes
    DATA_ROOT = Path(
        os.getenv(
            "DATA_ROOT",
            # Fallback only used in local dev if no .env and no env var
            BASE_DIR.parent / "collection-data"
        )
    )

    # Derived paths — never override these directly
    DB_PATH = DATA_ROOT / "collection.db"
    MIXTAPE_DIR = DATA_ROOT / "mixtapes"
    COVER_DIR = MIXTAPE_DIR / "covers"

    # Cache directory audio
    AUDIO_CACHE_DIR = DATA_ROOT / "cache" / "audio"

    # Keep password handling clean
    PASSWORD = os.getenv("PASSWORD", "dev-password")

    # Audio caching settings
    AUDIO_CACHE_ENABLED = True
    AUDIO_CACHE_DEFAULT_QUALITY = "medium"
    AUDIO_CACHE_MAX_WORKERS = 4
    AUDIO_CACHE_PRECACHE_ON_UPLOAD = True
    AUDIO_CACHE_PRECACHE_QUALITIES = ["medium"]  # Can add ["low", "medium", "high"]


    @classmethod
    def ensure_dirs(cls):
        """Create all required data and cache directories if they do not exist.

        This method prepares the filesystem so the application can safely store
        databases, mixtapes, covers, and cached audio files.
        """
        cls.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        cls.MIXTAPE_DIR.mkdir(parents=True, exist_ok=True)
        cls.COVER_DIR.mkdir(parents=True, exist_ok=True)
        cls.AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    """Development configuration used when running the app locally.

    This configuration enables debugging and uses local defaults suitable for
    iterative development.
    """
    DEBUG = True
    PASSWORD = os.getenv("PASSWORD", "dev-password")


class TestConfig(BaseConfig):
    """Test configuration tailored for running the application's automated tests.

    This configuration isolates test data and music paths to avoid affecting
    development or production environments.
    """
    PASSWORD = "test-password"
    DATA_ROOT = Path("/tmp/mixtape-test-data")  # isolated for tests
    MUSIC_ROOT = Path("/tmp/test-music")


class ProductionConfig(BaseConfig):
    """Production configuration for running the app in deployed environments.

    This configuration relies solely on environment variables and disables
    development-focused settings like debugging.
    """
    DEBUG = False
    # In production we trust only environment variables (set via docker-compose)
    PASSWORD = os.getenv("PASSWORD")