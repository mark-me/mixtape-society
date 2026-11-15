"""Checks the JavaScript and CSS libraries the templates load from CDNs for known vulnerabilities.

Dependabot and Trivy only see package files, not the pinned addresses in src/templates. This
reads those addresses, writes them as a package.json, and asks npm audit about them.

Only advisories for the libraries themselves count. Their own dependencies are what npm would
install for Node, not what the browser loads: a library's browser build bundles what it needs.

Exits with 1 when a library the templates load has a vulnerability of moderate severity or
worse, listing it; with 0 otherwise.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "templates"

# cdnjs names a library differently from npm now and then
CDNJS_TO_NPM = {"Sortable": "sortablejs"}

FAILING = {"moderate", "high", "critical"}

ADDRESS = re.compile(
    r"https://cdn\.jsdelivr\.net/npm/(?P<npm>(?:@[^/@\"]+/)?[^/@\"]+)@(?P<npm_version>[^/\"]+)"
    r"|https://cdnjs\.cloudflare\.com/ajax/libs/(?P<cdnjs>[^/\"]+)/(?P<cdnjs_version>[^/\"]+)/"
)


def libraries() -> dict[str, str]:
    """The libraries the templates load, by npm name, with their version."""
    found = {}
    for page in sorted(TEMPLATES.glob("*.html")):
        for match in ADDRESS.finditer(page.read_text(encoding="utf-8")):
            if match["npm"]:
                found[match["npm"]] = match["npm_version"]
            else:
                found[CDNJS_TO_NPM.get(match["cdnjs"], match["cdnjs"])] = match["cdnjs_version"]
    return found


def audit(found: dict[str, str]) -> dict:
    """npm audit's report for these libraries at these versions."""
    with tempfile.TemporaryDirectory() as folder:
        package = {"name": "cdn-libraries", "version": "1.0.0", "private": True, "dependencies": found}
        Path(folder, "package.json").write_text(json.dumps(package))
        subprocess.run(
            ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=folder,
            check=True,
            capture_output=True,
        )
        report = subprocess.run(["npm", "audit", "--json"], cwd=folder, capture_output=True, text=True)
        return json.loads(report.stdout)


def main() -> int:
    found = libraries()
    if not found:
        print("No CDN libraries found in the templates; has the address format changed?")
        return 1
    for name, version in sorted(found.items()):
        print(f"{name}@{version}")

    vulnerable = []
    for name, entry in audit(found)["vulnerabilities"].items():
        advisories = [via for via in entry["via"] if isinstance(via, dict)]
        if name not in found or not advisories:
            print(f"(a dependency for Node, not in the browser files: {name}, {entry['severity']})")
            continue
        for advisory in advisories:
            if advisory["severity"] in FAILING:
                vulnerable.append(
                    f"{name}@{found[name]}: {advisory['severity']} - {advisory['title']} ({advisory['url']})"
                )

    for line in vulnerable:
        print(f"VULNERABLE {line}")
    return 1 if vulnerable else 0


if __name__ == "__main__":
    sys.exit(main())
