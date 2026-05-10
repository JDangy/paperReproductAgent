from __future__ import annotations

"""Load and render logo/logo.png as Rich Text frames for Textual splash."""

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
FRAME_HEIGHT = 12
CHARS = " .:-=+*#%@"


def has_pil() -> bool:
    return HAS_PIL


def logo_exists() -> bool:
    return LOGO_PATH.exists()


def _resize_image(img) -> object:
    """Resize image to fit terminal frame while preserving aspect ratio."""
    w, h = img.size
    scale = min(FRAME_WIDTH / w, FRAME_HEIGHT * 2 / h)
    new_w = max(4, int(w * scale))
    new_h = max(4, int(h * scale / 2))
    return img.resize((new_w, new_h), Image.LANCZOS)  # type: ignore[union-attr]


def _pixel_to_char(gray: int) -> str:
    idx = int(gray / 256 * len(CHARS))
    return CHARS[min(idx, len(CHARS) - 1)]


def load_logo_text() -> Text:
    """Load logo and convert to Rich Text (static frame)."""
    if not HAS_PIL or not LOGO_PATH.exists():
        return _fallback_logo()

    try:
        img = Image.open(LOGO_PATH).convert("L")
        img = _resize_image(img)
        lines: list[str] = []
        for y in range(img.height):
            row = "".join(_pixel_to_char(img.getpixel((x, y))) for x in range(img.width))
            lines.append(row)
        text = Text()
        for i, line in enumerate(lines):
            if i > 0:
                text.append("\n")
            text.append(line, style="dim #6c7086")
        return text
    except Exception:
        return _fallback_logo()


def _fallback_logo() -> Text:
    return Text("Paper\nReproduct\nAgent", style="bold #bd93f9", justify="center")
