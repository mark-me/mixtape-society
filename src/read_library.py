#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
from tinytag import TinyTag
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import MultifieldParser, FuzzyTermPlugin

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==================== CONFIG ====================
MUSIC_ROOT = Path("/home/mark/Music")          # WIJZIG DIT
INDEX_DIR  = Path("./music_index")

EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wav", ".wma"}

# ==================== SCHEMA ====================
schema = Schema(
    path=ID(stored=True, unique=True),
    artist=TEXT(stored=True, phrase=False),
    album=TEXT(stored=True, phrase=False),
    title=TEXT(stored=True, phrase=False),
)

def get_tags(filepath: Path):
    """Extracts and returns the artist, album, and title tags from an audio file.

    This function reads metadata from the given file and provides fallback values based on the file path if tags are missing.

    Args:
        filepath (Path): The path to the audio file.

    Returns:
        tuple: A tuple containing the artist, album, and title as lowercase strings.
    """
    try:
        tag = TinyTag.get(filepath, tags=True, duration=False, image=False)
    except Exception:
        tag = None
    artist = (tag.artist or tag.albumartist or "").strip() or filepath.parent.parent.name
    album = (tag.album or "").strip() or filepath.parent.name
    title = (tag.title or filepath.stem).strip()
    return artist.lower(), album.lower(), title.lower()

# ==================== INDEX FUNCTIES ====================
def build_initial_index():
    """Builds a new search index for the entire music library.

    This function scans all supported audio files in the music root directory, extracts their tags, and creates a new Whoosh index.

    Returns:
        whoosh.index.Index: The newly created Whoosh index object.
    """
    print("Eerste volledige scan en indexering...")
    if INDEX_DIR.exists():
        import shutil
        shutil.rmtree(INDEX_DIR)
    os.makedirs(INDEX_DIR)

    ix = create_in(INDEX_DIR, schema)
    writer = ix.writer()

    count = 0
    for file_path in MUSIC_ROOT.rglob("*"):
        if file_path.suffix.lower() in EXTENSIONS and file_path.is_file():
            artist, album, title = get_tags(file_path)
            writer.add_document(
                path=str(file_path),
                artist=artist,
                album=album,
                title=title,
            )
            count += 1
            if count % 1000 == 0:
                print(f"  {count} bestanden...")

    writer.commit()
    print(f"Volledige index gebouwd: {count} tracks\n")
    return ix

def get_index():
    """Returns the Whoosh index for the music library, creating it if necessary.

    This function loads the existing index from disk or builds a new one if it does not exist.

    Returns:
        whoosh.index.Index: The Whoosh index object for the music library.
    """
    if not INDEX_DIR.exists() or not exists_in(INDEX_DIR):
        return build_initial_index()
    print("Bestaande index geladen.\n")
    return open_dir(INDEX_DIR)

# ==================== ZOEKEN ====================
def search(query_str: str, limit: int = 100, fuzziness: int = None):
    """Searches the music index for tracks matching the query string.

    This function performs a search across artist, album, and title fields, optionally using fuzzy matching, and returns a list of matching tracks with their metadata.

    Args:
        query_str (str): The search query string.
        limit (int, optional): The maximum number of results to return. Defaults to 100.
        fuzziness (int, optional): The fuzziness level for fuzzy searching. Defaults to None.

    Returns:
        list: A list of dictionaries containing artist, album, title, and path for each matching track.
    """
    ix = open_dir(INDEX_DIR)
    with ix.searcher() as searcher:
        parser = MultifieldParser(["artist", "album", "title"], ix.schema)
        parser.add_plugin(FuzzyTermPlugin())
        if fuzziness is not None:
            query = parser.parse(f"{query_str}~{fuzziness}")
        else:
            query = parser.parse(query_str)

        results = searcher.search(query, limit=limit), #sortedby="score")
        hits = []
        for hit in results:
            try:
                tag = TinyTag.get(hit['path'])
                artist = tag.artist or tag.albumartist or Path(hit['path']).parent.parent.name
                album  = tag.album or Path(hit['path']).parent.name
                title  = tag.title or Path(hit['path']).stem
            except Exception:
                artist = hit['artist'].title()
                album  = hit['album'].title()
                title  = hit['title'].title()

            hits.append({
                "artist": artist,
                "album":  album,
                "title":  title,
                "path":   hit['path'],
            })
        return hits

# ==================== WATCHDOG HANDLER ====================
class MusicWatcher(FileSystemEventHandler):
    """Handles file system events for the music library and updates the search index.

    This class listens for file creation, modification, movement, and deletion events, and updates the music index accordingly.
    """

    def __init__(self, index):
        """Initializes the MusicHandler with a reference to the search index.

        Args:
            index: The Whoosh index object to update in response to file system events.
        """
        self.ix = index

    def on_created(self, event):
        """Handles file creation events and updates the music index.

        This method is called when a new file is created in the monitored directory and adds it to the search index if it is a supported audio file.

        Args:
            event: The file system event object describing the creation.
        """
        if event.is_directory:
            return
        self.process(event.src_path)

    def on_modified(self, event):
        """Handles file modification events and updates the music index.

        This method is called when a file is modified in the monitored directory and updates the search index if it is a supported audio file.

        Args:
            event: The file system event object describing the modification.
        """
        if event.is_directory:
            return
        self.process(event.src_path)

    def on_moved(self, event):
        """Handles file move events and updates the music index.

        This method is called when a file is moved or renamed in the monitored directory.
        It removes the old entry from the search index and adds or updates the new one if it is a supported audio file.

        Args:
            event: The file system event object describing the move.
        """
        if event.is_directory:
            return
        # Verwijder oude, voeg nieuwe toe
        if Path(event.src_path).suffix.lower() in EXTENSIONS:
            self.delete_from_index(event.src_path)
        self.process(event.dest_path)

    def on_deleted(self, event):
        """Handles file deletion events and updates the music index.

        This method is called when a file is deleted in the monitored directory and removes it from the search index if it is a supported audio file.

        Args:
            event: The file system event object describing the deletion.
        """
        if event.is_directory:
            return
        self.delete_from_index(event.src_path)

    def process(self, path_str: str):
        """Indexes or updates a single audio file in the music index.

        This method extracts tags from the given file and updates the search index, replacing any previous entry for the same path.

        Args:
            path_str (str): The path to the audio file to process.
        """
        path = Path(path_str)
        if path.suffix.lower() not in EXTENSIONS or not path.is_file():
            return

        artist, album, title = get_tags(path)

        writer = self.ix.writer()
        # Verwijder eventueel oude versie (bij rename / tag change )
        writer.delete_by_term('path', str(path))
        writer.add_document(path=str(path), artist=artist, album=album, title=title)
        writer.commit()
        print(f"Indexed/Updated: {artist} – {title}")

    def delete_from_index(self, path_str: str):
        """Removes a file from the music index if it exists.

        This method deletes the entry for the given file path from the search index if it is a supported audio file.

        Args:
            path_str (str): The path to the audio file to remove from the index.
        """
        path = Path(path_str)
        if path.suffix.lower() not in EXTENSIONS:
            return
        writer = self.ix.writer()
        deleted = writer.delete_by_term('path', str(path))
        writer.commit()
        if deleted:
            print(f"Deleted from index: {path_str}")

# ==================== MAIN ====================
def main():
    ix = get_index()

    # Start de live watcher
    event_handler = MusicWatcher(ix)
    observer = Observer()
    observer.schedule(event_handler, str(MUSIC_ROOT), recursive=True)
    observer.start()
    print(f"Live monitoring gestart op {MUSIC_ROOT}")
    print("Typ je zoekterm (of 'quit' om te stoppen):\n")

    try:
        while True:
            query = input("> ").strip()
            if query.lower() in {"quit", "exit", "q"}:
                break
            if not query:
                continue

            start = time.time()
            results = search(query)
            took = time.time() - start

            print(f"\n{len(results)} resultaten in {took:.3f}s:\n")
            for r in results[:50]:
                print(f"{r['artist']} ─ {r['album']} ─ {r['title']}")
            if len(results) > 50:
                print(f"... en {len(results)-50} meer")
            print()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        print("\nTot ziens!")

if __name__ == "__main__":
    main()