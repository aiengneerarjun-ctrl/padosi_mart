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


# ---------------- ID / KYC document photo ----------------
DOC_MAX_SIDE = 1600  # ID ka likha hua padhne layak rahe, par file bhari na ho


def process_document_image(data: bytes) -> bytes:
    """ID / licence photo check karke ek WebP me badalta hai (square nahi karta, crop nahi karta).
    Re-encode se EXIF / location data hat jaata hai. Checks process_image jaise hi hain."""
    try:
        img = Image.open(BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise ImageError("IMAGE_FORMAT_NOT_ALLOWED", "Sirf JPG, PNG ya WebP chalegi.")
        if img.width * img.height > MAX_PIXELS:
            raise ImageError("IMAGE_TOO_LARGE", "Photo bahut badi hai.", 413)
        img.load()
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageError("IMAGE_INVALID", "Ye file sahi photo nahi hai.")

    img = ImageOps.exif_transpose(img)
    if min(img.size) < MIN_SIDE:
        raise ImageError("IMAGE_TOO_SMALL", "Photo bahut chhoti hai.")

    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    if max(img.size) > DOC_MAX_SIDE:
        img.thumbnail((DOC_MAX_SIDE, DOC_MAX_SIDE), Image.LANCZOS)  # ratio badle bina chhota karta hai
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=85, method=4)
    return buf.getvalue()