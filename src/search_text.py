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

    print("Indexing complete (or not needed). Searching...")
    result = collection.search_highlighting(query="Sea")
    return result

if __name__ == "__main__":
    result = main()
    print(result)