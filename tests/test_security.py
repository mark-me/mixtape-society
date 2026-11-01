"""Tests for the security headers and for refusing changes sent from other sites."""

import pytest

from conftest import PASSWORD


def test_every_answer_carries_the_security_headers(client):
    headers = client.get("/").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"
    assert "camera=()" in headers["Permissions-Policy"]


def test_the_content_security_policy_only_reports_for_now(client):
    headers = client.get("/").headers

    assert "default-src 'self'" in headers["Content-Security-Policy-Report-Only"]
    assert "Content-Security-Policy" not in headers


def test_the_help_has_no_content_security_policy(client):
    assert "Content-Security-Policy-Report-Only" not in client.get("/help/").headers


def test_the_session_cookie_stays_on_this_site(client):
    cookie = client.post("/auth/login", data={"password": "wrong"}).headers["Set-Cookie"]

    assert "SameSite=Lax" in cookie
    assert "HttpOnly" in cookie


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
    ],
)
def test_a_change_from_another_site_is_refused(owner, headers):
    assert owner.post("/resync", headers=headers).status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "same-origin"},
        {"Sec-Fetch-Site": "none"},
        {"Origin": "http://localhost"},
        {},
    ],
)
def test_a_change_from_the_app_itself_passes(client, headers):
    response = client.post("/auth/login", data={"password": PASSWORD}, headers=headers)

    assert response.status_code == 302


def test_reading_from_another_site_is_not_refused(client):
    assert client.get("/robots.txt", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200
