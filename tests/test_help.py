"""Tests for the help: the documentation site within the app, and its links in the menu."""

import re
from pathlib import Path

import pytest
from flask import Flask

from routes.help import ONLINE, create_help_blueprint

ROOT = Path(__file__).parent.parent


@pytest.fixture
def site(tmp_path):
    site = tmp_path / "site"
    (site / "user").mkdir(parents=True)
    (site / "index.html").write_text("home")
    (site / "user" / "index.html").write_text("user")
    (tmp_path / "secret.txt").write_text("secret")
    return site


def _client(help_dir):
    app = Flask(__name__)
    app.register_blueprint(create_help_blueprint(help_dir=help_dir), url_prefix="/help")
    return app.test_client()


def test_the_built_site_is_served(site):
    client = _client(site)

    assert client.get("/help/").data == b"home"
    assert client.get("/help/user/index.html").data == b"user"
    assert client.get("/help/nothing.html").status_code == 404


def test_a_folder_goes_to_its_page_so_relative_links_work(site):
    client = _client(site)

    assert client.get("/help/user").headers["Location"] == "/help/user/"
    assert client.get("/help/user/").data == b"user"


def test_nothing_outside_the_site_is_served(site):
    assert _client(site).get("/help/%2e%2e/secret.txt").status_code == 404


def test_without_a_built_site_the_help_comes_from_github_pages(tmp_path):
    response = _client(tmp_path / "none").get("/help/user/index.html")

    assert response.headers["Location"] == f"{ONLINE}user/index.html"


def test_the_help_needs_no_login(client):
    assert client.get("/help/").status_code == 302
    assert client.get("/help/").headers["Location"] == ONLINE


def test_every_help_link_in_the_menu_has_a_page():
    template = (ROOT / "src" / "templates" / "base.html").read_text()
    pages = re.findall(r"url_for\('help\.page', path='([^']+)\.html'\)", template)

    assert pages
    for page in pages:
        assert (ROOT / "docs" / f"{page}.md").is_file(), page


def test_the_menu_links_to_the_help_within_the_app(client):
    assert 'href="/help/user/recipients/index.html"' in client.get("/").get_data(as_text=True)


def test_the_owner_gets_the_creators_help(owner):
    assert 'href="/help/user/creators/index.html"' in owner.get("/mixtapes/").get_data(as_text=True)
