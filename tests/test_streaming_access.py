"""Tests for who may stream what, and for seeing a visitor's own address behind proxies."""

import json
import os
from pathlib import Path

import pytest
from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from security import trust_proxies

MUSIC = Path(os.environ["MUSIC_ROOT"])


@pytest.fixture
def library(app):
    folder = MUSIC / "Access"
    folder.mkdir(exist_ok=True)
    for name in ("shared.mp3", "private.mp3"):
        (folder / name).write_bytes(b"ID3 audio")
    mixtape = Path(app.config["MIXTAPE_DIR"]) / "access-test.json"
    mixtape.write_text(json.dumps({"title": "Access", "tracks": [{"path": "Access/shared.mp3"}]}))
    yield folder, mixtape
    mixtape.unlink(missing_ok=True)
    for file in folder.iterdir():
        file.unlink()
    folder.rmdir()


def test_a_track_in_a_mixtape_can_be_streamed_without_logging_in(client, library):
    assert client.get("/play/Access/shared.mp3").status_code == 200


def test_the_rest_of_the_collection_cannot(client, library):
    assert client.get("/play/Access/private.mp3").status_code == 404


def test_a_file_that_does_not_exist_looks_the_same(client, library):
    assert client.get("/play/Access/nothing.mp3").status_code == 404


def test_the_owner_can_stream_any_track_as_the_editor_previews_them(owner, library):
    assert owner.get("/play/Access/private.mp3").status_code == 200


def test_a_newly_saved_mixtape_can_be_streamed_at_once(client, library):
    _, mixtape = library
    mixtape.write_text(json.dumps({"title": "Access", "tracks": [{"path": "Access/private.mp3"}]}))

    assert client.get("/play/Access/private.mp3").status_code == 200
    assert client.get("/play/Access/shared.mp3").status_code == 404


def test_a_deleted_mixtape_can_no_longer_be_streamed(client, library):
    _, mixtape = library
    mixtape.unlink()

    assert client.get("/play/Access/shared.mp3").status_code == 404


def test_nothing_outside_the_collection_can_be_streamed(client, library):
    assert client.get("/play/Access/../../etc/passwd").status_code in (403, 404)


def _address_app(proxies: int) -> Flask:
    app = Flask(__name__)
    limiter = Limiter(get_remote_address, app=app)

    @app.post("/login")
    @limiter.limit("5 per minute")
    def login():
        return request.remote_addr

    trust_proxies(app, proxies)
    return app


def _attempts(app: Flask, forwarded_for: str) -> list[int]:
    client = app.test_client()
    client.environ_base["REMOTE_ADDR"] = "10.9.9.9"  # The proxy
    return [client.post("/login", headers={"X-Forwarded-For": forwarded_for}).status_code for _ in range(6)]


def test_behind_a_proxy_each_visitor_has_their_own_login_limit():
    app = _address_app(proxies=1)

    assert _attempts(app, "203.0.113.1")[-1] == 429
    assert _attempts(app, "203.0.113.2")[0] == 200
    assert app.test_client().post("/login", headers={"X-Forwarded-For": "203.0.113.3"}).text == "203.0.113.3"


def test_without_proxies_a_made_up_address_does_not_get_around_the_limit():
    app = _address_app(proxies=0)
    client = app.test_client()
    client.environ_base["REMOTE_ADDR"] = "198.51.100.7"

    codes = [client.post("/login", headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code for n in range(6)]

    assert codes[-1] == 429


def test_the_app_trusts_no_proxy_unless_told():
    from config import BaseConfig

    assert BaseConfig.TRUSTED_PROXIES == 0
