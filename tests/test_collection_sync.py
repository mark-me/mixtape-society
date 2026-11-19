"""Tests for keeping the collection in step with the music folder: resync, and lost file events."""

import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

from musiclib import _extractor
from musiclib._extractor import CollectionExtractor
from musiclib._watcher import add_overflow_listener, remove_overflow_listener
from musiclib.indexing_status import clear_indexing_status, set_indexing_status


def _song(path: Path, title: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-metadata", f"title={title}", "-metadata", "artist=Artist", "-metadata", "album=Album", "-y", str(path)],
        check=True,
    )
    return path


def _titles(extractor: CollectionExtractor) -> dict[str, str]:
    with extractor.get_conn(readonly=True) as conn:
        return {row["path"]: row["title"] for row in conn.execute("SELECT path, title FROM tracks")}


@pytest.fixture
def extractor(tmp_path):
    music = tmp_path / "music"
    _song(music / "Artist" / "Album" / "01 Song.mp3", "Old title")
    _song(music / "Artist" / "Album" / "02 Gone.mp3", "Gone")
    collection = CollectionExtractor(music, tmp_path / "data" / "collection.db")
    collection.rebuild()
    yield collection
    collection.stop()


def test_resync_reads_a_file_again_when_it_changed_on_disk(extractor):
    song = extractor.music_root / "Artist" / "Album" / "01 Song.mp3"
    _song(song, "New title")
    later = time.time() + 10
    os.utime(song, (later, later))

    extractor.resync()

    assert _titles(extractor)["Artist/Album/01 Song.mp3"] == "New title"


def test_resync_adds_new_files_and_drops_removed_ones(extractor):
    _song(extractor.music_root / "Artist" / "Album" / "03 New.mp3", "New")
    (extractor.music_root / "Artist" / "Album" / "02 Gone.mp3").unlink()

    extractor.resync()

    assert set(_titles(extractor)) == {"Artist/Album/01 Song.mp3", "Artist/Album/03 New.mp3"}


def _overflow_from_the_kernel() -> list:
    """Reads an inotify queue overflow event the way watchdog reads the kernel's events.

    A real overflow depends on how fast the machine reads compared with how fast files change,
    which differs per machine; this is the event the kernel sends when it happens.
    """
    from watchdog.observers.inotify_c import Inotify, InotifyConstants

    event = struct.pack("iIII", -1, InotifyConstants.IN_Q_OVERFLOW, 0, 0)
    return list(Inotify._parse_event_buffer(event))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify is Linux only")
def test_an_inotify_queue_overflow_is_noticed():
    noticed = []
    listener = lambda: noticed.append(True)  # noqa: E731
    add_overflow_listener(listener)
    try:
        events = _overflow_from_the_kernel()
    finally:
        remove_overflow_listener(listener)

    assert noticed == [True]
    assert [wd for wd, *_ in events] == [-1]


def _wait_for(condition, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


@pytest.fixture
def quick_resync(monkeypatch, extractor):
    monkeypatch.setattr(_extractor, "OVERFLOW_RESYNC_DELAY", 0.3)
    resyncs = []
    monkeypatch.setattr(extractor, "resync", lambda: resyncs.append(time.monotonic()))
    return extractor, resyncs


def test_a_burst_of_overflows_leads_to_one_resync_once_it_is_over(quick_resync):
    extractor, resyncs = quick_resync

    for _ in range(5):
        extractor._schedule_overflow_resync()

    assert _wait_for(lambda: resyncs)
    time.sleep(_extractor.OVERFLOW_RESYNC_DELAY * 3)
    assert len(resyncs) == 1


def test_the_resync_waits_while_indexing_runs(quick_resync):
    extractor, resyncs = quick_resync
    set_indexing_status(extractor.data_root, "rebuilding", total=10, current=1)

    extractor._schedule_overflow_resync()
    time.sleep(_extractor.OVERFLOW_RESYNC_DELAY * 3)
    assert resyncs == []

    clear_indexing_status(extractor.data_root)
    assert _wait_for(lambda: resyncs)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify is Linux only")
def test_monitoring_resyncs_after_file_events_were_lost(quick_resync):
    extractor, resyncs = quick_resync
    extractor.start_monitoring()

    _overflow_from_the_kernel()

    assert _wait_for(lambda: resyncs)
