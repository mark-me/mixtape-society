import re
from pathlib import Path

from .reader import MusicCollection


class MusicCollectionUI(MusicCollection):
    """UI/presentation layer – extends core with highlighting, reasons, rich formatting."""
    def __init__(self, music_root, db_path, logger=None):
        super().__init__(music_root, db_path, logger)

    def search_highlighting(self, query: str, limit: int = 30) -> list[dict]:
        """
        Searches the music collection and highlights matching terms in the results.

        Returns a list of search results with highlighted artist, album, and track fields based on the query terms.

        Args:
            query (str): The search string to match and highlight in the music library.
            limit (int, optional): The maximum number of results to return. Defaults to 30.

        Returns:
            list[dict]: A list of search result dictionaries with highlighted text.
        """
        if not query.strip():
            return {"artists": [], "albums": [], "tracks": []}

        # Simple quote handling: if query has quotes, extract inside as exact phrase
        quoted = re.findall(r'"([^"]*)"', query)
        plain = re.sub(r'"[^"]*"', '', query).strip()
        terms = quoted + (plain.split() if plain else [])
        term_pat = re.compile("|".join(map(re.escape, filter(None, terms))), re.I)

        # Use your existing grouped search but with better terms
        grouped, _ = self.search_grouped(query, limit=limit)

        # Highlight artists
        cache: dict[str, str] = {}
        def hl(text: str) -> str:
            if text not in cache:
                cache[text] = term_pat.sub(r"<mark>\g<0></mark>", text)
            return cache[text]

        # Walk the result tree
        for artist in grouped["artists"]:
            artist["artist"] = hl(artist["artist"])
            for album in artist.get("albums", []):
                album["album"] = hl(album["album"])
                for track in album.get("tracks", []):
                    track["track"] = hl(track["track"])

        for album in grouped["albums"]:
            album["artist"] = hl(album["artist"])
            album["album"] = hl(album["album"])
            for track in album.get("tracks", []):
                track["track"] = hl(track["track"])

        for track in grouped["tracks"]:
            track["artist"] = hl(track["artist"])
            track["album"] = hl(track["album"])
            track["track"] = hl(track["track"])

        return grouped


    def highlight_text(self, text: str, queries: list[str]) -> str:
        """
        Highlights occurrences of search queries within a text string using HTML markup.

        Wraps each matching query substring in <mark> tags for display purposes, returning the highlighted text.

        Args:
            text (str): The input text to highlight.
            queries (list[str]): A list of query strings to highlight in the text.

        Returns:
            str: The text with matching queries wrapped in <mark> tags.
        """
        if not queries:
            return text
        # Sort queries by descending length to prioritize longer matches
        sorted_queries = sorted((q for q in queries if q), key=len, reverse=True)
        pattern = "|".join(re.escape(q) for q in sorted_queries)
        return re.sub(f"({pattern})", r"<mark>\1</mark>", text, flags=re.I)