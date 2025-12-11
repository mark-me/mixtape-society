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
    # 1. Music library location
    MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/home/mark/Music"))

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

    # Keep password handling clean
    PASSWORD = os.getenv("PASSWORD", "dev-password")

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        cls.MIXTAPE_DIR.mkdir(parents=True, exist_ok=True)
        cls.COVER_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    PASSWORD = os.getenv("PASSWORD", "dev-password")


class TestConfig(BaseConfig):
    PASSWORD = "test-password"
    DATA_ROOT = Path("/tmp/mixtape-test-data")  # isolated for tests
    MUSIC_ROOT = Path("/tmp/test-music")


class ProductionConfig(BaseConfig):
    DEBUG = False
    # In production we trust only environment variables (set via docker-compose)
    PASSWORD = os.getenv("PASSWORD")