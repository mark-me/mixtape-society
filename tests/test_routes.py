"""Tests for the routes of the app as a whole."""

import pytest


@pytest.mark.parametrize(
    ("path", "mimetype"),
    [
        ("/manifest.json", "application/manifest+json"),
        ("/service-worker.js", "application/javascript"),
        ("/robots.txt", "text/plain"),
        ("/indexing-status", "application/json"),
    ],
)
def test_public_files_are_served(client, path, mimetype):
    response = client.get(path)

    assert response.status_code == 200
    assert response.mimetype == mimetype


def test_the_service_worker_is_scoped_to_the_player(client):
    assert client.get("/service-worker.js").headers["Service-Worker-Allowed"] == "/play/"


@pytest.mark.parametrize("path", ["/collection-stats", "/check-database-health", "/mixtapes/"])
def test_the_owners_pages_ask_for_a_login(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize("path", ["/resync", "/reset-database"])
def test_maintenance_asks_for_a_login(client, path):
    assert client.post(path).status_code == 302


def test_the_owner_sees_the_collection_stats(owner):
    assert "num_tracks" in owner.get("/collection-stats").get_json()


def test_the_owner_sees_the_database_health(owner):
    assert owner.get("/check-database-health").get_json()["healthy"] is True


def test_covers_only_serve_images(client):
    assert client.get("/covers/config.py").status_code == 404
