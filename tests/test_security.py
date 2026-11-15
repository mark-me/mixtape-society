"""Tests for the security headers, for refusing changes sent from other sites, and for what
reaches a page or the audio cache without a login."""

import re
from pathlib import Path

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


ATTACK = '<script>alert(document.cookie)</script><img src=x onerror=alert(1)>'


@pytest.mark.parametrize("template", ["gift-playful.html", "gift-elegant.html"])
@pytest.mark.parametrize("field", ["gift_note", "liner_notes"])
def test_markup_in_a_gift_note_is_shown_as_text(app, template, field):
    from flask import render_template

    mixtape = {"slug": "tape", "title": "Tape", "tracks": [], "cover": None, "liner_notes": ""}
    note = ATTACK if field == "gift_note" else ""
    if field == "liner_notes":
        mixtape["liner_notes"] = ATTACK
    with app.test_request_context("/play/gift-playful/tape"):
        page = render_template(template, mixtape=mixtape, slug="tape", gift_note=note,
                               receiver_name="", from_name="", is_gift=True)

    assert "<script>alert" not in page
    assert "<img src=x" not in page
    assert "&lt;script&gt;alert(document.cookie)&lt;/script&gt;" in page


def test_no_template_writes_markup_unescaped():
    templates = Path(__file__).parent.parent / "src" / "templates"
    unescaped = [
        f"{page.name}:{number}"
        for page in templates.glob("*.html")
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1)
        for use in re.findall(r"[^{]*\|\s*safe\b", line)
        if "tojson" not in use
    ]

    assert unescaped == []


@pytest.fixture
def cached_file(app):
    cached = Path(app.config["AUDIO_CACHE_DIR"]) / "0123456789abcdef_medium_192k.mp3"
    cached.write_bytes(b"audio")
    yield cached
    cached.unlink(missing_ok=True)


def test_the_audio_cache_cannot_be_cleared_without_logging_in(client, cached_file):
    response = client.post("/play/admin/cache/clear")

    assert response.status_code == 302
    assert cached_file.exists()


def test_the_audio_cache_figures_need_a_login(client):
    assert client.get("/play/admin/cache/stats").status_code == 302


def test_the_owner_can_clear_the_audio_cache(owner, cached_file):
    response = owner.post("/play/admin/cache/clear")

    assert response.status_code == 200
    assert not cached_file.exists()


# Google serves these itself and changes them, so they can't be pinned or hashed.
UNPINNABLE_HOSTS = {"fonts.googleapis.com", "www.gstatic.com"}


def _external_resources():
    templates = Path(__file__).parent.parent / "src" / "templates"
    for page in templates.glob("*.html"):
        for tag in re.findall(r"<(?:script|link)\b[^>]*>", page.read_text(encoding="utf-8")):
            url = re.search(r'(?:src|href)="(https://[^"]+)"', tag)
            if url and ("<script" in tag or 'rel="stylesheet"' in tag):
                yield page.name, tag, url.group(1)


def test_every_script_and_stylesheet_from_elsewhere_is_pinned_and_checked():
    resources = list(_external_resources())
    assert resources

    unchecked = []
    for page, tag, url in resources:
        host = url.split("/")[2]
        if host in UNPINNABLE_HOSTS:
            continue
        pinned = re.search(r"@\d+\.\d+\.\d+|/ajax/libs/[^/]+/\d+\.\d+\.\d+/", url)
        checked = 'integrity="sha384-' in tag and 'crossorigin="anonymous"' in tag
        if not (pinned and checked):
            unchecked.append(f"{page}: {url}")

    assert unchecked == []


def test_bootstrap_is_loaded_once():
    loads = [url for _, _, url in _external_resources() if url.endswith("bootstrap.bundle.min.js")]

    assert len(loads) == 1
