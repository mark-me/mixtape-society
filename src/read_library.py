#!/usr/bin/env python3
import sqlite3
import time
from pathlib import Path
from tinytag import TinyTag
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==================== CONFIG ====================
MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"
# ===============================================

class MusicCollection:
    def __init__(self, music_root: Path, db_path: Path):
        self.music_root = music_root.resolve()
        self.db_path = db_path.resolve()
        self.supported = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    artist TEXT,
                    album TEXT,
                    title TEXT,
                    albumartist TEXT,
                    genre TEXT,
                    year INTEGER,
                    duration REAL
                )
            """)
            for idx in [
                "CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_album  ON tracks(album  COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_title  ON tracks(title  COLLATE NOCASE)"
            ]:
                conn.execute(idx)

    def db_ready(self):
        return self.db_path.exists() and self.count_tracks() > 0

    def count_tracks(self):
        with self.get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

    def rebuild(self):
        print("Scanning and indexing your music collection...")
        self._ensure_schema()
        with self.get_conn() as conn:
            conn.execute("DELETE FROM tracks")
            count = 0
            start = time.time()
            for fp in self.music_root.rglob("*.*"):
                if fp.is_file() and fp.suffix.lower() in self.supported:
                    try:
                        self._index_file(conn, fp)
                    except Exception as e:
                        print(f"Warning: Skipping {fp.name}: {e}")
                    count += 1
                    if count % 3000 == 0:
                        print(f"   Processed {count:,} files...")
            conn.commit()
        print(f"Done! Indexed {count:,} files in {time.time()-start:.1f}s\n")

    def _safe_int_year(self, value):
        if not value: return None
        if isinstance(value, int): return value
        if isinstance(value, float): return int(value) if value == int(value) else None
        s = str(value).strip().split('-', 1)[0].split('.', 1)[0]
        return int(s) if s.isdigit() else None

    def _index_file(self, conn, path: Path):
        tag = None
        try:
            tag = TinyTag.get(path, tags=True, duration=True)
        except:
            pass

        artist = (getattr(tag, "artist", None) or getattr(tag, "albumartist", None) or
                  path.parent.parent.name or "Unknown").strip()
        album = (getattr(tag, "album", None) or path.parent.name or "Unknown").strip()
        title = (getattr(tag, "title", None) or path.stem).strip()

        year = self._safe_int_year(getattr(tag, "year", None))
        duration = None
        if tag and getattr(tag, "duration", None):
            try:
                duration = float(tag.duration)
            except:
                pass

        conn.execute("""INSERT OR REPLACE INTO tracks
            (path, filename, artist, album, title, albumartist, genre, year, duration)
            VALUES (?,?,?,?,?,?,?,?,?)""", (
            str(path), path.name, artist, album, title,
            getattr(tag, "albumartist", None),
            getattr(tag, "genre", None),
            year, duration
        ))

    def search_grouped(self, query: str, limit: int = 20):
        if not (q := query.strip()):
            return {"artists": [], "albums": [], "tracks": []}

        like_pat = f"%{q}%"
        starts_pat = f"{q}%"

        with self.get_conn() as conn:
            result = {"artists": [], "albums": [], "tracks": []}

            # 1. ARTISTS
            cur = conn.execute("""
                SELECT DISTINCT artist FROM tracks
                WHERE artist LIKE ? COLLATE NOCASE
                ORDER BY artist LIKE ? DESC, artist COLLATE NOCASE
                LIMIT ?
            """, (starts_pat, starts_pat, limit))
            result["artists"] = [{"artist": r["artist"]} for r in cur]

            # 2. ALBUMS
            skip = {a["artist"].lower() for a in result["artists"]}
            if skip:
                placeholders = ",".join("?" for _ in skip)
                sql = f"""
                    SELECT DISTINCT artist, album FROM tracks
                    WHERE album LIKE ? COLLATE NOCASE
                      AND lower(artist) NOT IN ({placeholders})
                    ORDER BY album LIKE ? DESC, album COLLATE NOCASE
                    LIMIT ?
                """
                # like, starts, *skip (strings), limit (int) → correct order!
                cur = conn.execute(sql, (like_pat, starts_pat, *skip, limit))
            else:
                cur = conn.execute("""
                    SELECT DISTINCT artist, album FROM tracks
                    WHERE album LIKE ? COLLATE NOCASE
                    ORDER BY album LIKE ? DESC, album COLLATE NOCASE
                    LIMIT ?
                """, (like_pat, starts_pat, limit))
            result["albums"] = [{"artist": r["artist"], "album": r["album"]} for r in cur]

            # 3. TRACKS
            skip.update(a["artist"].lower() for a in result["albums"])
            if skip:
                placeholders = ",".join("?" for _ in skip)
                sql = f"""
                    SELECT artist, album, title AS track FROM tracks
                    WHERE title LIKE ? COLLATE NOCASE
                      AND lower(artist) NOT IN ({placeholders})
                    ORDER BY title LIKE ? DESC, title COLLATE NOCASE
                    LIMIT ?
                """
                cur = conn.execute(sql, (like_pat, starts_pat, *skip, limit))
            else:
                cur = conn.execute("""
                    SELECT artist, album, title AS track FROM tracks
                    WHERE title LIKE ? COLLATE NOCASE
                    ORDER BY title LIKE ? DESC, title COLLATE NOCASE
                    LIMIT ?
                """, (like_pat, starts_pat, limit))
            result["tracks"] = [{"artist": r["artist"], "album": r["album"], "track": r["track"]} for r in cur]

        return result


class MusicWatcher(FileSystemEventHandler):
    def __init__(self, collection): self.collection = collection
    def on_any_event(self, event):
        if event.is_directory: return
        path = Path(getattr(event, "src_path", None) or getattr(event, "dest_path", None) or "")
        if not path.exists() or path.suffix.lower() not in self.collection.supported: return
        with self.collection.get_conn() as conn:
            if event.event_type == "deleted":
                conn.execute("DELETE FROM tracks WHERE path = ?", (str(path),))
            else:
                try:
                    self.collection._index_file(conn, path)
                except:
                    pass
            conn.commit()


# ==================== MAIN ====================
if __name__ == "__main__":
    if not MUSIC_ROOT.exists():
        print(f"ERROR: Music folder not found: {MUSIC_ROOT}")
        exit(1)

    collection = MusicCollection(MUSIC_ROOT, DB_PATH)
    print(f"Music folder : {MUSIC_ROOT}")
    print(f"Database     : {DB_PATH}\n")

    if not collection.db_ready():
        collection.rebuild()
    else:
        print(f"Library ready — {collection.count_tracks():,} tracks loaded\n")

    observer = Observer()
    observer.schedule(MusicWatcher(collection), str(MUSIC_ROOT), recursive=True)
    observer.start()
    print("Live monitoring active — type to search (q to quit)\n")

    try:
        while True:
            q = input("> ").strip()
            if q.lower() in {"q", "quit", "exit"}: break
            if not q: continue

            t0 = time.time()
            result = collection.search_grouped(q, limit=20)
            t = time.time() - t0

            print(f"\nResults in {t:.3f}s\n")

            if result["artists"]:
                print("ARTISTS:")
                for a in result["artists"][:10]:
                    print(f"  • {a['artist']}")
                if len(result["artists"]) > 10:
                    print(f"  ... +{len(result['artists'])-10} more")

            if result["albums"]:
                print("\nALBUMS:")
                for a in result["albums"][:10]:
                    print(f"  • {a['artist']} — {a['album']}")
                if len(result["albums"]) > 10:
                    print(f"  ... +{len(result['albums'])-10} more")

            if result["tracks"]:
                print("\nTRACKS:")
                for t in result["tracks"][:15]:
                    print(f"  • {t['artist']} — {t['album']} — {t['track']}")
                if len(result["tracks"]) > 15:
                    print(f"  ... +{len(result['tracks'])-15} more")

            if not any(result.values()):
                print("  No results found.")

            print("\n" + "─" * 50)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        observer.stop()
        observer.join()
        print("Bye!")