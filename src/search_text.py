from pathlib import Path
from logtools import get_logger

from musiclib import MusicCollectionUI, get_indexing_status

def main():

    logger = get_logger(__name__)

    path_music = Path("/home/mark/Music")
    path_db = Path("collection-data/collection.db")
    collection = MusicCollectionUI(music_root=path_music, db_path=path_db, logger=logger)

    data_root = path_db.parent.resolve()

    # Wait while indexing is in progress
    while collection.is_indexing():
        status = get_indexing_status(data_root=data_root, logger=logger)

        if status is None:
            # No indexing in progress → we can search safely
            break

        if status.get("status") not in ("rebuilding", "resyncing"):
            # Unexpected status, but not rebuilding/resyncing → stop waiting
            break

        print(f"Indexing in progress: {status['status']} "
              f"({status['current']}/{status['total']} – {status['progress']*100:.1f}%)")

    with collection._get_conn() as conn:
        cur = conn.execute("SELECT artist, album FROM tracks WHERE lower(album) LIKE '%firstborn%'")
        print("Albums with 'firstborn':", cur.fetchall())

    print("Indexing complete (or not needed). Searching...")
    result = collection.search_highlighting(query="artist:'Nick Cave'")
    result = collection.search_highlighting(query="artist:Nick album:\"Firstborn\"")
    result = collection.search_highlighting(query="Nick")
    result = collection.search_highlighting(query="song:\"Weeping Song\"")
    result = collection.search_highlighting(query="song: \"Weeping Song\"")
    return result

if __name__ == "__main__":
    result = main()
    print(result)