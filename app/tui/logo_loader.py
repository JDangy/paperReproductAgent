from __future__ import annotations

"""Load and render logo/logo.png as Rich Text for Textual splash."""

from pathlib import Path
from rich.text import Text

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from app.core.paths import find_project_root

LOGO_PATH = find_project_root() / "logo" / "logo.png"
FRAME_WIDTH = 50
FRAME_HEIGHT = 14
CHARS = " .:-=+*#%@"


def has_pil() -> bool:
    return HAS_PIL


def logo_exists() -> bool:
    return LOGO_PATH.exists()


def _pixel_to_char(gray: int, alpha: int = 255) -> str:
    if alpha < 128:
        return " "
    darkness = 255 - gray
    idx = int(darkness / 256 * len(CHARS))
    return CHARS[min(idx, len(CHARS) - 1)]


def _crop_white_border(img: "Image.Image") -> "Image.Image":
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img


def _resize_image(img: "Image.Image", lines: int = FRAME_HEIGHT) -> "Image.Image":
    w, h = img.size
    scale = min(FRAME_WIDTH / w, lines * 2 / h)
    new_w = max(4, int(w * scale))
    new_h = max(4, int(h * scale / 2))
    return img.resize((new_w, new_h), Image.LANCZOS)


def load_logo_text(lines: int = FRAME_HEIGHT) -> Text:
    """Load logo and convert to Rich Text (static frame)."""
    if not HAS_PIL or not LOGO_PATH.exists():
        return _fallback_logo()

    try:
        img = Image.open(LOGO_PATH)

        if img.mode == "RGBA":
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg

        img = _crop_white_border(img)
        img = img.convert("L")
        img = _resize_image(img, lines)

        text_lines: list[str] = []
        for y in range(img.height):
            row = "".join(_pixel_to_char(img.getpixel((x, y))) for x in range(img.width))
            text_lines.append(row)

        text = Text()
        for i, line in enumerate(text_lines):
            if i > 0:
                text.append("\n")
            text.append(line, style="#bd93f9")
        return text
    except Exception:
        return _fallback_logo()


def _fallback_logo() -> Text:
    return Text("", style="dim")