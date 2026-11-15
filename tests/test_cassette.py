"""Tests for the cassette sound: the TDK D90 version of a track that cassette mode plays."""

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import pytest

import audio_cache.audio_cache as audio_cache_module
from app import saved_track_paths
from audio_cache import AudioCache, CacheWorker
from mixtape_manager import MixtapeManager


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


def test_a_file_being_written_is_not_served_as_cached(tmp_path, cache, monkeypatch):
    source = tmp_path / "song.flac"
    source.write_bytes(b"source")
    final = cache.get_cache_path(source, "cassette")
    seen = {}

    def ffmpeg(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"half")
        seen["cached while writing"] = cache.is_cached(source, "cassette")
        seen["final file while writing"] = final.exists()
        Path(cmd[-1]).write_bytes(b"whole")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audio_cache_module.subprocess, "run", ffmpeg)
    cache.transcode_file(source, "cassette")

    assert seen == {"cached while writing": False, "final file while writing": False}
    assert final.read_bytes() == b"whole"


def test_two_jobs_making_the_same_file_do_not_write_into_each_other(tmp_path, cache, monkeypatch):
    source = tmp_path / "song.flac"
    source.write_bytes(b"source")
    both_writing = threading.Barrier(2, timeout=5)
    written_to = []

    def ffmpeg(cmd, **kwargs):
        written_to.append(cmd[-1])
        both_writing.wait()
        Path(cmd[-1]).write_bytes(b"whole")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audio_cache_module.subprocess, "run", ffmpeg)
    jobs = [threading.Thread(target=cache.transcode_file, args=(source, "cassette", True)) for _ in range(2)]
    for job in jobs:
        job.start()
    for job in jobs:
        job.join()

    assert len(set(written_to)) == 2
    assert cache.get_cache_path(source, "cassette").read_bytes() == b"whole"
    assert [path.name for path in cache.cache_dir.iterdir()] == [cache.get_cache_path(source, "cassette").name]


def test_clearing_removes_files_left_by_interrupted_jobs(cache):
    left = cache.cache_dir / "abc_cassette_192k.mp3.x1.part"
    writing = cache.cache_dir / "abc_cassette_192k.mp3.x2.part"
    for path in (left, writing):
        path.write_bytes(b"half")
    two_hours_ago = time.time() - 7200
    os.utime(left, (two_hours_ago, two_hours_ago))

    cache.clear_cache()

    assert not left.exists()
    assert writing.exists()


def test_mixtapes_saved_before_get_their_cassette_version(tmp_path, cache):
    source = _make_audio(tmp_path / "song.mp3", "sine=frequency=440:duration=2")

    CacheWorker(cache).regenerate_outdated_cache([source], ["medium", "cassette"])

    assert cache.is_cached(source, "cassette")


@pytest.fixture
def track(app):
    path = _make_audio(Path(os.environ["MUSIC_ROOT"]) / "cassette-route.flac", "sine=frequency=440:duration=2")
    # In a saved mixtape, as a recipient without a login may only stream those tracks
    mixtape = Path(app.config["MIXTAPE_DIR"]) / "cassette-route.json"
    mixtape.write_text(json.dumps({"title": "Cassette route", "tracks": [{"path": "cassette-route.flac"}]}))
    yield path
    mixtape.unlink()
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

    assert response.status_code == (206 if headers else 200)
    assert response.mimetype == "audio/flac"
    assert response.headers["Cache-Control"] == "no-store"
    if headers:
        assert response.headers["Content-Range"] == f"bytes 0-99/{track.stat().st_size}"
        assert len(response.data) == 100


def test_startup_skips_mixtapes_it_cannot_read(tmp_path):
    music = tmp_path / "music"
    music.mkdir()
    (music / "good.mp3").write_bytes(b"audio")
    mixtapes = tmp_path / "mixtapes"
    mixtapes.mkdir()
    saved = {
        "good": {"tracks": [{"path": "good.mp3"}, {"path": "gone.mp3"}]},
        "tracks-not-a-list": {"tracks": "good.mp3"},
        "track-without-path": {"tracks": [{"artist": "Someone"}, "good.mp3", {"path": 3}]},
    }
    for slug, data in saved.items():
        (mixtapes / f"{slug}.json").write_text(json.dumps(data))
    (mixtapes / "broken.json").write_text("{not json")

    paths = saved_track_paths(MixtapeManager(path_mixtapes=mixtapes, collection=None), music, logger=None)

    assert paths == [music / "good.mp3"]


def test_startup_goes_on_when_the_mixtapes_cannot_be_listed(tmp_path):
    class Unreadable:
        def list_all(self):
            raise TypeError("not a mixtape")

    class Logger:
        warned = []

        def warning(self, message):
            self.warned.append(message)

    logger = Logger()

    assert saved_track_paths(Unreadable(), tmp_path, logger) == []
    assert logger.warned
