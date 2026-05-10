from __future__ import annotations

"""Load and render logo/logo.png as animated Rich Text frames for Textual splash.

Implements the spinning ring logo with blue-white gradient,
based on the user-provided algorithm.
"""

import math
from pathlib import Path
from rich.text import Text

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from app.core.paths import find_project_root

SOURCE_IMAGE = find_project_root() / "logo" / "logo.png"

LINES = 30
FRAME_STEP = 15
FPS_INTERVAL = 0.08
CLOCKWISE = True

WHITE = (255, 255, 255)
CAS_BLUE = (23, 73, 148)

FILL_CHARS = " .:=*#%@"
OUTLINE_CHARS = ".,:;i1tfLCG08@"


def has_pil() -> bool:
    return HAS_PIL


def logo_exists() -> bool:
    return SOURCE_IMAGE.exists()


def _fallback_frame() -> Text:
    return Text("", style="dim")


def ansi_rgb(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def crop_white_border(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    x0, y0, x1, y1 = 0, 0, gray.width, gray.height
    for y in range(gray.height):
        if any(gray.getpixel((x, y)) < 240 for x in range(gray.width)):
            y0 = y
            break
    for y in range(gray.height - 1, -1, -1):
        if any(gray.getpixel((x, y)) < 240 for x in range(gray.width)):
            y1 = y + 1
            break
    for x in range(gray.width):
        if any(gray.getpixel((x, y)) < 240 for y in range(gray.height)):
            x0 = x
            break
    for x in range(gray.width - 1, -1, -1):
        if any(gray.getpixel((x, y)) < 240 for y in range(gray.height)):
            x1 = x + 1
            break
    return img.crop((x0, y0, x1, y1))


def load_source_image(image_path: Path | None = None) -> Image.Image:
    path = image_path or SOURCE_IMAGE
    img = Image.open(path)
    if img.mode == "RGBA":
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    img = crop_white_border(img)
    return img.convert("L")


def make_clean_ring_frame(
    img_gray: Image.Image,
    lines: int = LINES,
) -> Image.Image:
    aspect = img_gray.height / img_gray.width
    new_w = max(4, int(lines * 2 * (1 / max(aspect, 0.01))))
    new_h = max(4, lines * 2)
    scale = min(new_w / img_gray.width, new_h / img_gray.height)
    render_w = max(4, int(img_gray.width * scale))
    render_h = max(4, int(img_gray.height * scale))
    return img_gray.resize((render_w, render_h), Image.LANCZOS)


def render_outline_fill(img_gray: Image.Image) -> list[list[tuple[str, bool]]]:
    """Render each pixel as (char, is_outline) tuples."""
    w, h = img_gray.size
    grid = [[(255, False)] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            g = img_gray.getpixel((x, y))
            grid[y][x] = (g, g < 240)

    cells: list[list[tuple[str, bool]]] = []
    for y in range(h):
        row: list[tuple[str, bool]] = []
        for x in range(w):
            g, is_filled = grid[y][x]
            if not is_filled:
                row.append((" ", False))
                continue
            is_edge = False
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if ny < 0 or ny >= h or nx < 0 or nx >= w:
                    is_edge = True
                    break
                if not grid[ny][nx][1]:
                    is_edge = True
                    break
            if is_edge:
                idx = min(int((255 - g) / 256 * len(OUTLINE_CHARS)), len(OUTLINE_CHARS) - 1)
                row.append((OUTLINE_CHARS[idx], True))
            else:
                idx = min(int((255 - g) / 256 * len(FILL_CHARS)), len(FILL_CHARS) - 1)
                row.append((FILL_CHARS[idx], False))
        cells.append(row)
    return cells


def colorize_blue_white_gradient(
    cells: list[list[tuple[str, bool]]],
    ring_angle: float = 0.0,
) -> Text:
    """Apply blue-white gradient based on angular position + ring_angle offset."""
    h = len(cells)
    w = max(len(row) for row in cells) if cells else 1
    cx, cy = w / 2, h / 2
    text = Text()

    for y, row in enumerate(cells):
        for x, (ch, is_outline) in enumerate(row):
            if ch == " ":
                text.append(" ")
                continue
            dx = x - cx
            dy = y - cy
            angle = math.atan2(dy, dx)
            t = (angle + ring_angle) / (2 * math.pi) % 1.0
            r = int(WHITE[0] + (CAS_BLUE[0] - WHITE[0]) * t)
            g = int(WHITE[1] + (CAS_BLUE[1] - WHITE[1]) * t)
            b = int(WHITE[2] + (CAS_BLUE[2] - WHITE[2]) * t)
            if is_outline:
                r = min(255, r + 40)
                g = min(255, g + 40)
                b = min(255, b + 40)
            color = ansi_rgb(r, g, b)
            text.append(ch, style=color)
        if y < len(cells) - 1:
            text.append("\n")
    return text


def build_frames(
    image_path: Path | None = None,
    lines: int = LINES,
    frame_step: int = FRAME_STEP,
    clockwise: bool = CLOCKWISE,
) -> list[Text]:
    """Build all rotation frames of the logo as Rich Text objects."""
    if not HAS_PIL:
        return [_fallback_frame()]

    path = image_path or SOURCE_IMAGE
    if not path.exists():
        return [_fallback_frame()]

    try:
        img_gray = load_source_image(path)
    except Exception:
        return [_fallback_frame()]

    rendered = make_clean_ring_frame(img_gray, lines)
    cells = render_outline_fill(rendered)

    frames: list[Text] = []
    for deg in range(0, 360, frame_step):
        rad = math.radians(deg * (1 if clockwise else -1))
        frame = colorize_blue_white_gradient(cells, ring_angle=rad)
        frames.append(frame)
    return frames


def load_logo_text(lines: int = LINES) -> Text:
    """Load a single static logo frame (first frame, no rotation)."""
    frames = build_frames(lines=lines)
    return frames[0] if frames else _fallback_frame()


def load_logo_frames(
    image_path: Path | None = None,
    lines: int = LINES,
    frame_step: int = FRAME_STEP,
    clockwise: bool = CLOCKWISE,
) -> list[Text]:
    """Load all animated logo frames."""
    return build_frames(image_path=image_path, lines=lines, frame_step=frame_step, clockwise=clockwise)


def _pixel_to_char(gray: int, alpha: int = 255) -> str:
    if alpha < 128:
        return " "
    darkness = 255 - gray
    CHARS = " .:-=+*#%@"
    idx = int(darkness / 256 * len(CHARS))
    return CHARS[min(idx, len(CHARS) - 1)]