"""Tests for what the documentation build does not check itself."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"


def _pages(entries) -> list[str]:
    found = []
    for entry in entries:
        if isinstance(entry, str):
            found.append(entry)
        else:
            for value in entry.values():
                found += _pages(value) if isinstance(value, list) else [value]
    return found


def test_the_navigation_names_every_page_and_only_pages_that_exist():
    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))

    on_disk = sorted(page.relative_to(DOCS).as_posix() for page in DOCS.rglob("*.md"))

    assert sorted(_pages(config["project"]["nav"])) == on_disk


def test_every_image_on_a_page_exists():
    missing = []
    for page in DOCS.rglob("*.md"):
        text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        text = re.sub(r"`[^`\n]*`", "", text)
        for target in re.findall(r"!\[[^\]]*\]\(([^)\s]+)", text):
            if not re.match(r"[a-z]+:", target) and not (page.parent / target).is_file():
                missing.append(f"{page.relative_to(DOCS)}: {target}")

    assert missing == []


def test_the_help_needs_nothing_from_the_internet():
    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))["project"]
    stylesheet = DOCS / "stylesheets" / "extra.css"

    assert config["theme"]["font"] is False
    assert all((DOCS / script).is_file() for script in config["extra_javascript"])
    assert "javascripts/vendor/mermaid.min.js" in config["extra_javascript"]
    fonts = re.findall(r'url\("([^"]+)"\)', stylesheet.read_text(encoding="utf-8"))
    assert fonts
    assert all((stylesheet.parent / font).is_file() for font in fonts)
