from flask import Blueprint, render_template

from config import BaseConfig as Config
from musiclib import MusicCollection

play = Blueprint('play', __name__, template_folder='templates')


@play.route('/<title>')
def play_mixtape(title):
    music_collection = MusicCollection()
    mixtapes = music_collection.load_mixtapes()
    mixtape = next((m for m in mixtapes if m['title'] == title), None)
    if not mixtape:
        return "Mixtape not found", 404

    # Voeg full paths toe voor streaming
    for track in mixtape['tracks']:
        track['full_path'] = Config.MUSIC_ROOT / track['path']

    return render_template('play.html', mixtape=mixtape)