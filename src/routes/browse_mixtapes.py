from pathlib import Path

from flask import Blueprint, abort, render_template, send_from_directory

from mixtape_manager import MixtapeManager

browser = Blueprint("browse_mixtapes", __name__, template_folder="../templates")

MIXTAPE_PATH = Path(__file__).parent.parent.parent / "mixtapes"

@browser.route("/mixtapes")
def index():
    mixtape_manager = MixtapeManager(path_mixtapes=MIXTAPE_PATH)
    mixtapes = mixtape_manager.list_all()
    return render_template("browse_mixtapes.html", mixtapes=mixtapes)


@browser.route("/mixtapes/play/<title>")
def play(title):
    if mixtape := MixtapeManager.get(title):
        return render_template("play_mixtape.html", mixtape=mixtape, title=title)
    else:
        abort(404)

# Serve covers & andere bestanden
@browser.route("/mixtapes/files/<path:filename>")
def files(filename):
    return send_from_directory(MIXTAPE_PATH, filename)