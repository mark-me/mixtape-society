"""What the tests share: an app running on empty, temporary directories."""

import itertools
import os
import tempfile
import time

import pytest

# The configuration is read when it is imported, so this comes before any import of the app.
_root = tempfile.mkdtemp(prefix="mixtape-tests-")
os.environ.update(
    APP_ENV="development",
    PASSWORD="test-password",
    DATA_ROOT=os.path.join(_root, "data"),
    MUSIC_ROOT=os.path.join(_root, "music"),
    HELP_DIR=os.path.join(_root, "no-help"),
)
os.makedirs(os.environ["MUSIC_ROOT"])

PASSWORD = os.environ["PASSWORD"]
_addresses = itertools.count(1)


@pytest.fixture(scope="session")
def app():
    from app import create_app
    from musiclib import get_indexing_status

    app = create_app()
    # The app starts by indexing the (empty) music folder; a request during it gets the
    # indexing page, so wait until it is done.
    deadline = time.monotonic() + 30
    while get_indexing_status(os.environ["DATA_ROOT"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    return app


@pytest.fixture
def client(app):
    # Each client its own address, so the login limit of one test doesn't reach the next.
    client = app.test_client()
    client.environ_base["REMOTE_ADDR"] = f"10.0.0.{next(_addresses)}"
    return client


@pytest.fixture
def owner(client):
    client.post("/auth/login", data={"password": PASSWORD})
    return client
