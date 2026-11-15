"""Tests for the cassette sound: the TDK D90 version of a track that cassette mode plays."""

import os
import re
import subprocess
from pathlib import Path

import pytest

from audio_cache import AudioCache, CacheWorker


def _make_audio(path: Path, source: str) -> Path:
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", source, "-ac", "2", "-y", str(path)],
        check=True,
    )
    return path


def _loudness(path: Path) -> float:
    """The mean volume in dB; silence comes out at -91 dB or lower."""
    found = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    return float(re.search(r"mean_volume: (-?[\d.]+|-inf) dB", found).group(1).replace("-inf", "-200"))


@pytest.fixture
def cache(tmp_path):
    return AudioCache(tmp_path / "cache")


def test_the_cassette_version_is_made_for_mp3_too(tmp_path, cache):
    source = _make_audio(tmp_path / "song.mp3", "sine=frequency=440:duration=2")

    assert cache.transcode_file(source, "medium") == source
    cassette = cache.transcode_file(source, "cassette")
    assert cassette != source
    assert cassette.is_file()
    assert cache.is_cached(source, "cassette")


def test_the_cassette_version_adds_tape_hiss(tmp_path, cache):
    source = _make_audio(tmp_path / "silence.flac", "anullsrc=r=44100:cl=stereo:d=2")

    assert _loudness(cache.transcode_file(source, "medium")) < -90
    assert _loudness(cache.transcode_file(source, "cassette")) > -70


@pytest.mark.parametrize(("frequency", "lost"), [(1000, (-2, 2)), (18000, (15, 30))])
def test_the_cassette_version_keeps_the_middle_and_cuts_the_top(tmp_path, cache, frequency, lost):
    source = _make_audio(tmp_path / f"tone{frequency}.flac", f"sine=frequency={frequency}:duration=2")

    medium = _loudness(cache.transcode_file(source, "medium"))
    cassette = _loudness(cache.transcode_file(source, "cassette"))

    assert lost[0] < medium - cassette < lost[1]


def test_the_cassette_and_medium_versions_are_kept_apart(tmp_path, cache):
    source = tmp_path / "song.flac"

    assert cache.get_cache_path(source, "cassette") != cache.get_cache_path(source, "medium")


def test_only_finished_files_count_as_cached(tmp_path, cache):
    broken = tmp_path / "broken.flac"
    broken.write_bytes(b"not audio")

    with pytest.raises(subprocess.CalledProcessError):
        cache.transcode_file(broken, "cassette")

    assert not cache.is_cached(broken, "cassette")
    assert list(cache.cache_dir.iterdir()) == []


def test_mixtapes_saved_before_get_their_cassette_version(tmp_path, cache):
    source = _make_audio(tmp_path / "song.mp3", "sine=frequency=440:duration=2")

    CacheWorker(cache).regenerate_outdated_cache([source], ["medium", "cassette"])

    assert cache.is_cached(source, "cassette")


@pytest.fixture
def track(app):
    path = _make_audio(Path(os.environ["MUSIC_ROOT"]) / "cassette-route.flac", "sine=frequency=440:duration=2")
    yield path
    path.unlink()
    for made in Path(app.config["AUDIO_CACHE_DIR"]).iterdir():
        made.unlink()


def test_cassette_mode_plays_the_cassette_version(app, client, track):
    cassette = AudioCache(app.config["AUDIO_CACHE_DIR"]).transcode_file(track, "cassette")

    response = client.get("/play/cassette-route.flac?quality=cassette")

    assert response.mimetype == "audio/mpeg"
    assert response.data == cassette.read_bytes()
    assert "no-store" not in response.headers["Cache-Control"]


@pytest.mark.parametrize("headers", [{}, {"Range": "bytes=0-99"}])
def test_until_it_is_made_a_stand_in_plays_that_is_not_kept(client, track, headers):
    response = client.get("/play/cassette-route.flac?quality=cassette", headers=headers)

    assert response.status_code in (200, 206)
    assert response.mimetype == "audio/flac"
    assert response.headers["Cache-Control"] == "no-store"
