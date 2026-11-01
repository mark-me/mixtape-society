"""Tests for logging in and for the key that signs the session cookie."""

import stat
from types import SimpleNamespace

import pytest
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature

from auth import derive_session_key, password_matches
from conftest import PASSWORD


def _session_cookie(response) -> str:
    return response.headers["Set-Cookie"].split("session=", 1)[1].split(";", 1)[0]


def _signed_with(cookie: str, key: str) -> bool:
    signer = SecureCookieSessionInterface().get_signing_serializer(
        SimpleNamespace(secret_key=key, config={"SECRET_KEY_FALLBACKS": None})
    )
    try:
        signer.loads(cookie)
    except BadSignature:
        return False
    return True


def test_the_right_password_logs_in(client):
    client.post("/auth/login", data={"password": PASSWORD})

    assert client.get("/collection-stats").status_code == 200


@pytest.mark.parametrize("form", [{"password": "wrong"}, {"password": ""}, {}])
def test_anything_else_does_not(client, form):
    client.post("/auth/login", data=form)

    assert client.get("/collection-stats").status_code == 302


def test_a_session_cookie_cannot_be_used_to_guess_the_password(client):
    cookie = _session_cookie(client.post("/auth/login", data={"password": "wrong"}))

    assert not _signed_with(cookie, PASSWORD)


def test_the_app_signs_with_the_derived_key(app, client):
    cookie = _session_cookie(client.post("/auth/login", data={"password": "wrong"}))

    assert _signed_with(cookie, app.secret_key)


def test_the_key_stays_the_same_across_starts(tmp_path):
    assert derive_session_key(tmp_path, "a") == derive_session_key(tmp_path, "a")


def test_another_password_gives_another_key_so_everyone_is_logged_out(tmp_path):
    assert derive_session_key(tmp_path, "a") != derive_session_key(tmp_path, "b")


def test_only_the_owner_can_read_the_key_file(tmp_path):
    derive_session_key(tmp_path, "a")

    assert stat.S_IMODE((tmp_path / "session_key").stat().st_mode) == 0o600
    assert [path.name for path in tmp_path.iterdir()] == ["session_key"]


@pytest.mark.parametrize(
    ("submitted", "configured", "expected"),
    [
        ("secret", "secret", True),
        ("wáchtwoord", "wáchtwoord", True),
        ("wáchtwoord", "other", False),
        (None, None, False),
        ("", "", False),
        ("secret", None, False),
    ],
)
def test_password_matches(submitted, configured, expected):
    assert password_matches(submitted, configured) is expected


def test_the_app_does_not_start_without_a_password(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "get_configuration", lambda: SimpleNamespace(PASSWORD=None))

    with pytest.raises(RuntimeError, match="PASSWORD"):
        app_module.create_app()
