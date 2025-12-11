from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.parent

class BaseConfig:
    """
    Base configuration class for the application.

    Defines default paths and settings for music, database, mixtapes, covers, and password.
    Provides a method to ensure required directories exist.
    """
    MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/home/mark/Music"))
    DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "collection-data" / "music.db"))
    MIXTAPE_DIR = Path(os.getenv("MIXTAPE_DIR", BASE_DIR / "mixtapes"))
    COVER_DIR = MIXTAPE_DIR / "covers"
    PASSWORD = "password"#os.getenv("APP_PASSWORD", "dev-password")

    @classmethod
    def ensure_dirs(cls):
        """
        Ensures that the mixtape and cover directories exist.

        Creates the directories if they do not already exist.
        """
        cls.MIXTAPE_DIR.mkdir(exist_ok=True)
        cls.COVER_DIR.mkdir(exist_ok=True)


class DevelopmentConfig(BaseConfig):
    """
    Configuration class for development environment.

    Inherits from BaseConfig and enables debug mode.
    """
    DEBUG = True


class TestConfig(BaseConfig):
    """
    Configuration class for running tests.

    Inherits from BaseConfig and sets a test-specific password.
    """
    PASSWORD = "test-password"


class ProductionConfig(BaseConfig):
    """
    Configuration class for production deployment.

    Inherits from BaseConfig and disables debug mode.
    """
    DEBUG = False
