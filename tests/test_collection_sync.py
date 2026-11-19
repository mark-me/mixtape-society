"""Tests for keeping the collection in step with the music folder: resync, and lost file events."""

import os
import subprocess
import sys
import threading
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


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify is Linux only")
def test_an_inotify_queue_overflow_is_noticed(tmp_path):
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    noticed = threading.Event()
    listener = noticed.set
    add_overflow_listener(listener)
    observer = Observer()
    observer.schedule(FileSystemEventHandler(), str(tmp_path), recursive=True)
    observer.start()
    try:
        # More events than the kernel queues by default (16384), faster than they are read
        subprocess.run("seq 1 60000 | xargs touch", shell=True, cwd=tmp_path, check=True)
        assert noticed.wait(timeout=30)
    finally:
        remove_overflow_listener(listener)
        observer.stop()
        observer.join(timeout=10)


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
        time.sleep(0.1)
    time.sleep(1)

    assert len(resyncs) == 1


def test_the_resync_waits_while_indexing_runs(quick_resync):
    extractor, resyncs = quick_resync
    set_indexing_status(extractor.data_root, "rebuilding", total=10, current=1)

    extractor._schedule_overflow_resync()
    time.sleep(1)
    assert resyncs == []

    clear_indexing_status(extractor.data_root)
    time.sleep(1)
    assert len(resyncs) == 1


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify is Linux only")
def test_monitoring_resyncs_after_file_events_were_lost(quick_resync):
    extractor, resyncs = quick_resync
    extractor.start_monitoring()
    burst = extractor.music_root / "burst"
    burst.mkdir()

    subprocess.run("seq 1 60000 | xargs touch", shell=True, cwd=burst, check=True)
    deadline = time.monotonic() + 30
    while not resyncs and time.monotonic() < deadline:
        time.sleep(0.2)

    assert resyncs
