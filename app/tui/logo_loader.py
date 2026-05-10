from __future__ import annotations

"""Load and render logo/logo.png as animated Rich Text frames for Textual splash.

Implements the spinning ring logo with blue-white gradient.
The logo image is rotated via PIL, and the color gradient is fixed
in screen coordinates — no "clock hand" color sweep.
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


def real_rotation_angle(deg: int, clockwise: bool = True) -> int:
    """PIL rotates counter-clockwise for positive angles; clockwise needs negation."""
    return -deg if clockwise else deg


def crop_white_border(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    x0, y0, x1, y1 = 0, 0, gray.width, gray.height
    found = False
    for y in range(gray.height):
        if any(gray.getpixel((x, y)) < 240 for x in range(gray.width)):
            y0 = y
            found = True
            break
    found = False
    for y in range(gray.height - 1, -1, -1):
        if any(gray.getpixel((x, y)) < 240 for x in range(gray.width)):
            y1 = y + 1
            found = True
            break
    found = False
    for x in range(gray.width):
        if any(gray.getpixel((x, y)) < 240 for y in range(gray.height)):
            x0 = x
            found = True
            break
    found = False
    for x in range(gray.width - 1, -1, -1):
        if any(gray.getpixel((x, y)) < 240 for y in range(gray.height)):
            x1 = x + 1
            found = True
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


def _resize_to_fit(
    img_gray: Image.Image,
    lines: int = LINES,
    max_width: int | None = None,
) -> Image.Image:
    """Resize image to exactly `lines` text rows high, width capped by max_width."""
    src_w, src_h = img_gray.size
    aspect = src_w / src_h
    target_h = lines * 2
    target_w = max(4, int(target_h * aspect))
    if max_width is not None and target_w > max_width:
        target_w = max_width
        target_h = max(4, int(target_w / aspect))
        if target_h > lines * 2:
            target_h = lines * 2
    return img_gray.resize((target_w, target_h), Image.LANCZOS)


def make_clean_ring_frame(
    img_gray: Image.Image,
    lines: int = LINES,
    max_width: int | None = None,
) -> Image.Image:
    """Resize image to fit exactly `lines` rows, capped by max_width chars."""
    return _resize_to_fit(img_gray, lines=lines, max_width=max_width)


def render_outline_fill(
    img_gray: Image.Image,
    lines: int = LINES,
    max_width: int | None = None,
) -> list[str]:
    """Render gray image to ASCII lines. Returns list of strings, each exactly `lines` rows."""
    img = _resize_to_fit(img_gray, lines=lines, max_width=max_width)
    w, h = img.size

    grid = [[(255, False)] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            g = img.getpixel((x, y))
            grid[y][x] = (g, g < 240)

    ascii_lines: list[str] = []
    for y in range(h):
        row: list[str] = []
        for x in range(w):
            g, is_filled = grid[y][x]
            if not is_filled:
                row.append(" ")
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
                row.append(OUTLINE_CHARS[idx])
            else:
                idx = min(int((255 - g) / 256 * len(FILL_CHARS)), len(FILL_CHARS) - 1)
                row.append(FILL_CHARS[idx])
        ascii_lines.append("".join(row).rstrip())
    return ascii_lines


def colorize_blue_white_gradient(
    ascii_lines: list[str],
    width: int | None = None,
    height: int | None = None,
) -> Text:
    """Apply blue-white gradient using fixed screen-coordinate bounds.

    The gradient is computed from fixed (width, height) so it never
    shifts between frames — no "clock hand" sweep effect.
    """
    h = height or len(ascii_lines)
    w = width or max((len(line) for line in ascii_lines), default=1)

    text = Text()
    for y, line in enumerate(ascii_lines):
        padded = line.ljust(w)
        for x, ch in enumerate(padded):
            if ch == " ":
                text.append(" ")
                continue
            nx = x / max(1, w - 1)
            ny = y / max(1, h - 1)
            t = 0.15 + 0.35 * (0.55 * nx + 0.45 * ny)
            r = int(WHITE[0] + (CAS_BLUE[0] - WHITE[0]) * t)
            g = int(WHITE[1] + (CAS_BLUE[1] - WHITE[1]) * t)
            b = int(WHITE[2] + (CAS_BLUE[2] - WHITE[2]) * t)
            color = ansi_rgb(r, g, b)
            text.append(ch, style=color)
        if y < len(ascii_lines) - 1:
            text.append("\n")
    return text


def build_frames(
    image_path: Path | None = None,
    lines: int = LINES,
    frame_step: int = FRAME_STEP,
    clockwise: bool = CLOCKWISE,
    max_width: int | None = None,
) -> list[Text]:
    """Build all rotation frames of the logo as Rich Text objects.

    Each frame rotates the SOURCE IMAGE via PIL, then renders to ASCII,
    then applies a FIXED-BOUNDS gradient. No color sweep.
    Result: exactly `lines` rows per frame.
    """
    if not HAS_PIL:
        return [_fallback_frame()]

    path = image_path or SOURCE_IMAGE
    if not path.exists():
        return [_fallback_frame()]

    try:
        src_gray = load_source_image(path)
    except Exception:
        return [_fallback_frame()]

    frames: list[Text] = []
    for deg in range(0, 360, frame_step):
        angle = real_rotation_angle(deg, clockwise)
        rotated = src_gray.rotate(angle, resample=Image.BICUBIC, expand=True)
        rotated = crop_white_border(rotated)

        ascii_lines = render_outline_fill(rotated, lines=lines, max_width=max_width)

        while len(ascii_lines) < lines:
            ascii_lines.append("")
        ascii_lines = ascii_lines[:lines]

        fixed_w = max(len(line) for line in ascii_lines) if ascii_lines else 1
        frame = colorize_blue_white_gradient(ascii_lines, width=fixed_w, height=lines)
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
    max_width: int | None = None,
) -> list[Text]:
    """Load all animated logo frames."""
    return build_frames(
        image_path=image_path,
        lines=lines,
        frame_step=frame_step,
        clockwise=clockwise,
        max_width=max_width,
    )


def _pixel_to_char(gray: int, alpha: int = 255) -> str:
    if alpha < 128:
        return " "
    darkness = 255 - gray
    CHARS = " .:-=+*#%@"
    idx = int(darkness / 256 * len(CHARS))
    return CHARS[min(idx, len(CHARS) - 1)]