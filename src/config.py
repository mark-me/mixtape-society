from pathlib import Path
import os

BASE_DIR = Path(__file__).parent

class BaseConfig:
    """
    Base configuration class for the application.

    Defines default paths and settings for music, database, mixtapes, covers, and password.
    Provides a method to ensure required directories exist.
    """
    MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/data/music"))
    DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "collection-data" / "music.db"))
    MIXTAPE_DIR = Path(os.getenv("MIXTAPE_DIR", BASE_DIR / "mixtapes"))
    COVER_DIR = MIXTAPE_DIR / "covers"
    PASSWORD = os.getenv("APP_PASSWORD", "dev-password")

    @classmethod
    def ensure_dirs(cls):
        """
        Ensures that the mixtape and cover directories exist.

        Creates the directories if they do not already exist.
        """
        cls.MIXTAPE_DIR.mkdir(exist_ok=True)
        cls.COVER_DIR.mkdir(exist_ok=True)


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    PASSWORD = "test-password"


class ProductionConfig(BaseConfig):
    DEBUG = False
