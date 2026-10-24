"""Test di image_utils.py (M01, NF02): contenuto reale, HEIC, EXIF, 1024 px, tutto in memoria."""

import io

import pytest
from PIL import Image

from conftest import make_image
from image_utils import InvalidImage, prepare_image


def _open(data):
    return Image.open(io.BytesIO(data))


@pytest.mark.parametrize("fmt,name", [("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp"), ("HEIF", "a.heic")])
def test_formati_ammessi_diventano_jpeg(fmt, name):
    out = _open(prepare_image(make_image(fmt), name))
    assert out.format == "JPEG" and out.mode == "RGB"


def test_ridimensionata_a_1024():
    out = _open(prepare_image(make_image("JPEG", size=(4000, 3000)), "grande.jpg"))
    assert max(out.size) == 1024 and out.size == (1024, 768)


def test_piccola_non_ingrandita():
    assert _open(prepare_image(make_image("PNG", size=(300, 200)), "p.png")).size == (300, 200)


def test_rotazione_exif():
    # Orientamento 6 = foto scattata in verticale: larghezza e altezza vanno scambiate
    out = _open(prepare_image(make_image("JPEG", size=(400, 200), exif_orientation=6), "r.jpg"))
    assert out.size == (200, 400)


def test_contenuto_verificato_non_l_estensione():
    with pytest.raises(InvalidImage, match="non è un'immagine valida"):
        prepare_image(b"testo qualsiasi, non una foto", "finta.jpg")


def test_formato_non_ammesso():
    with pytest.raises(InvalidImage, match="Formato non supportato"):
        prepare_image(make_image("GIF"), "animazione.gif")


def test_file_vuoto():
    with pytest.raises(InvalidImage, match="vuota"):
        prepare_image(b"", "vuota.jpg")


def test_immagine_enorme_bloccata():
    with pytest.raises(InvalidImage, match="risoluzione troppo alta"):
        prepare_image(make_image("PNG", size=(9000, 9000), color=(0, 0, 0)), "enorme.png")
