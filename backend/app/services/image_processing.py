"""Upload hui photo ko check karke 3 size ki WebP me badalta hai. DB/storage se koi lena-dena nahi."""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PIXELS = 25_000_000  # bahut bade (decompression bomb) image se server bachane ke liye
MIN_SIDE = 400  # isse chhoti photo blurry dikhegi
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
SIZES = {"thumb": 256, "medium": 640, "large": 1280}  # square (1:1), listing card ke liye


class ImageError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status


@dataclass
class ProcessedImage:
    variants: dict[str, bytes]  # {"thumb": webp bytes, ...}
    width: int
    height: int


def process_image(data: bytes) -> ProcessedImage:
    try:
        img = Image.open(BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise ImageError("IMAGE_FORMAT_NOT_ALLOWED", "Sirf JPG, PNG ya WebP chalegi.")
        if img.width * img.height > MAX_PIXELS:
            raise ImageError("IMAGE_TOO_LARGE", "Photo bahut badi hai.", 413)
        img.load()  # asli decode yahin hota hai; kharab file yahin pakdi jaati hai
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageError("IMAGE_INVALID", "Ye file sahi photo nahi hai.")

    img = ImageOps.exif_transpose(img)  # mobile photo ka ghuma hua orientation seedha karo
    width, height = img.size
    if min(width, height) < MIN_SIDE:
        raise ImageError("IMAGE_TOO_SMALL", "Photo bahut chhoti hai.")

    # Transparent PNG ko safed background par rakho; re-encode se EXIF/location data bhi hat jaata hai
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    # Square (1:1): product ko kaata nahi jaata, bas safed jagah jodi jaati hai
    side = max(width, height)
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(img, ((side - width) // 2, (side - height) // 2))

    variants: dict[str, bytes] = {}
    for name, px in SIZES.items():
        out = canvas if side <= px else canvas.resize((px, px), Image.LANCZOS)  # chhoti photo ko bada nahi karte
        buf = BytesIO()
        out.save(buf, format="WEBP", quality=75 if name == "thumb" else 82, method=4)
        variants[name] = buf.getvalue()
    return ProcessedImage(variants=variants, width=width, height=height)