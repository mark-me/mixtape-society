from pathlib import Path

def to_relative_path(abs_path: str | Path, music_root: str | Path) -> str:
    """Converteert absoluut pad naar pad relatief t.o.v. MUSIC_ROOT (met forward slashes)"""
    abs_path = Path(abs_path).resolve()
    music_root = Path(music_root).resolve()
    if not str(abs_path).startswith(str(music_root)):
        raise ValueError(f"Bestand ligt niet in MUSIC_ROOT: {abs_path}")
    rel = abs_path.relative_to(music_root)
    return str(rel).replace("\\", "/")