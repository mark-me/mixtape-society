from flask import Blueprint, render_template

from config import BaseConfig as Config
from musiclib import MusicCollection

play = Blueprint('play', __name__, template_folder='templates')


@play.route('/<title>')
def play_mixtape(title):
    """
    Renders the playback page for a mixtape with the given title.

    Loads the mixtape by title, adds full file paths for streaming, and renders the playback template. Returns a 404 error if the mixtape is not found.

    Args:
        title: The title of the mixtape to play.

    Returns:
        Response: The rendered playback page or a 404 error if not found.
    """
    music_collection = MusicCollection()
    mixtapes = music_collection.load_mixtapes()
    mixtape = next((m for m in mixtapes if m['title'] == title), None)
    if not mixtape:
        return "Mixtape not found", 404

    # Voeg full paths toe voor streaming
    for track in mixtape['tracks']:
        track['full_path'] = Config.MUSIC_ROOT / track['path']

    return render_template('play.html', mixtape=mixtape)