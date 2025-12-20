from pathlib import Path

from musiclib import MusicCollection

def main():
    path_music = Path("/home/mark/Music")
    path_db = Path("collection-data/collection.db")
    collection = MusicCollection(music_root=path_music, db_path=path_db)
    result = collection.search_highlighting(query="Nick")
    print(result)

if __name__ == "__main__":
    main()