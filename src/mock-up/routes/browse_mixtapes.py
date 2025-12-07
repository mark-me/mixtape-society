from flask import Blueprint, render_template, send_from_directory, abort
from musiclib import MixtapeManager
from pathlib import Path

browser = Blueprint("browse_mixtapes", __name__, template_folder="../templates")

@browser.route("/mixtapes")
def index():
    mixtapes = MixtapeManager.list_all()
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
    return send_from_directory(Path(__file__).parent.parent.parent / "mixtapes", filename)