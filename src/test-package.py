from pathlib import Path
from musiclib import MusicCollection


MUSIC_ROOT = Path("/home/mark/Music")
DB_PATH = Path(__file__).parent.parent / "collection-data" / "music.db"

# One-liner — everything just works
with MusicCollection(music_root=MUSIC_ROOT, db_path=DB_PATH) as lib:
    print(f"Library has {lib.count():,} tracks")
    results = lib.search_grouped(query="Nick")
    tracks = lib.search(artist="Nick Cave", album="Discovery")
    for track in tracks:
        print(f"{track['title']} – {track['duration']:.0f}s")