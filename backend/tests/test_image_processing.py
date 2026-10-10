from io import BytesIO

import pytest
from PIL import Image

from app.services.image_processing import ImageError, process_image


def _img(size=(800, 600), mode="RGB", fmt="JPEG", color=(200, 30, 30)):
    buf = BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt)
    return buf.getvalue()


def _decode(blob):
    return Image.open(BytesIO(blob))


def test_makes_three_square_webp_sizes():
    out = process_image(_img((1600, 900)))
    assert (out.width, out.height) == (1600, 900)
    for name, px in {"thumb": 256, "medium": 640, "large": 1280}.items():
        im = _decode(out.variants[name])
        assert im.format == "WEBP" and im.size == (px, px)


def test_small_image_is_not_upscaled():
    out = process_image(_img((500, 500)))
    assert _decode(out.variants["large"]).size == (500, 500)
    assert _decode(out.variants["thumb"]).size == (256, 256)


def test_padding_is_white_not_cropped():
    im = _decode(process_image(_img((1000, 500), color=(0, 0, 0))).variants["large"]).convert("RGB")
    assert im.getpixel((640, 10))[0] > 240  # upar ki patti safed
    assert im.getpixel((640, 640))[0] < 15  # beech me product


def test_transparent_png_gets_white_background():
    data = _img((600, 600), mode="RGBA", fmt="PNG", color=(0, 0, 0, 0))
    im = _decode(process_image(data).variants["medium"]).convert("RGB")
    assert im.getpixel((10, 10))[0] > 240


@pytest.mark.parametrize(
    "data,code",
    [
        (b"not an image at all", "IMAGE_INVALID"),
        (_img((300, 300)), "IMAGE_TOO_SMALL"),
        (_img((600, 600), fmt="GIF", mode="P"), "IMAGE_FORMAT_NOT_ALLOWED"),
        (_img((600, 600), fmt="BMP"), "IMAGE_FORMAT_NOT_ALLOWED"),
    ],
)
def test_bad_images_rejected(data, code):
    with pytest.raises(ImageError) as exc:
        process_image(data)
    assert exc.value.code == code


def test_truncated_file_rejected():
    with pytest.raises(ImageError) as exc:
        process_image(_img((900, 900))[:300])
    assert exc.value.code == "IMAGE_INVALID"
    