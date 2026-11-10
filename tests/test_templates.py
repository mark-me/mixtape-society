"""Tests for the templates: every URL they ask for exists, and the pages render."""

import re
import subprocess
from pathlib import Path

import pytest
from flask import render_template

SRC = Path(__file__).parent.parent / "src"


def _endpoints_asked_for() -> list[tuple[str, str]]:
    found = subprocess.run(
        ["git", "grep", "-n", "-oE", r"""url_for\(\s*['"][^'"]+""", "--", "templates", "routes", "app.py"],
        cwd=SRC,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    asked = []
    for line in found.splitlines():
        place, _, call = line.rpartition(":")
        asked.append((place, re.sub(r"""url_for\(\s*['"]""", "", call)))
    return asked


def test_every_url_for_names_an_endpoint_that_exists(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    asked = _endpoints_asked_for()

    assert asked
    missing = [f"{place}: {name}" for place, name in asked if not name.startswith(".") and name not in endpoints]
    assert missing == []


@pytest.fixture
def mixtape():
    return {
        "slug": "test-tape",
        "title": "Test tape",
        "cover": "covers/test-tape.jpg",
        "liner_notes": "",
        "created_at": "2026-11-01T12:00:00",
        "updated_at": "2026-11-01T12:00:00",
        "tracks": [
            {
                "artist": "Artist",
                "album": "Album",
                "track": "Track",
                "duration": "3:00",
                "path": "Artist/Album/01 Track.flac",
                "filename": "01 Track.flac",
                "cover": "covers/Artist_Album.jpg",
            }
        ],
    }


def test_the_public_player_shows_track_covers(app, mixtape):
    with app.test_request_context("/play/share/test-tape"):
        page = render_template("play_mixtape.html", mixtape=mixtape, public=True)

    assert 'src="/covers/Artist_Album.jpg"' in page


def test_the_indexing_page_renders(app):
    status = {"status": "rebuilding", "current": 1, "total": 10, "progress": 0.1, "started_at": None}
    with app.test_request_context("/"):
        page = render_template("indexing.html", status=status)

    assert '"/indexing-status"' in page


def test_the_owners_play_link_goes_to_the_public_player(owner):
    response = owner.get("/mixtapes/play/test-tape")

    assert response.status_code == 302
    assert response.headers["Location"] == "/play/share/test-tape"
