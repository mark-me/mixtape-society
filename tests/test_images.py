"""Tests for what is made with Pillow and CairoSVG: QR codes, social-share images, and reloading."""

import io
from pathlib import Path

from PIL import Image

from musiclib import MusicCollectionUI
from qr_generator.qr_generator import generate_mixtape_qr
from routes import logo_on_cover

LOGO = Path(__file__).parent.parent / "src" / "static" / "images" / "logo.svg"


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_a_qr_code_is_a_png_of_the_asked_size():
    image = Image.open(io.BytesIO(generate_mixtape_qr(url="https://example.org/play/a", title="A", size=400)))

    assert image.format == "PNG"
    assert image.size == (400, 400)


def test_a_share_image_fits_the_social_card_size():
    cover = logo_on_cover._prepare_cover(_jpeg(800, 600))

    assert logo_on_cover._create_blurred_canvas(cover).size == (1200, 630)


def test_the_logo_is_rendered_from_svg():
    logo = logo_on_cover._prepare_logo(LOGO.read_bytes(), (800, 600), 0.2)

    assert logo.width > 0


def test_reloading_keeps_the_collection_usable(tmp_path):
    collection = MusicCollectionUI(music_root=tmp_path, db_path=tmp_path / "collection.db")
    try:
        collection.reload()

        assert collection.count() == 0
    finally:
        collection.close()
