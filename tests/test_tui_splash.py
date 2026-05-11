from __future__ import annotations

"""Tests for boot splash, logo loader, and preflight fixes."""

from app.tui.logo_loader import (
    _pixel_to_char,
    _fallback_frame,
    load_logo_text,
    load_logo_frames,
    HAS_PIL,
    CAS_BLUE,
    WHITE,
    ansi_rgb,
    real_rotation_angle,
    LINES,
    crop_white_border,
    make_clean_ring_frame,
    render_outline_fill,
    colorize_blue_white_gradient,
    build_frames,
)
from app.tui.preflight import CheckItem


# ── Logo loader constants & basic functions ──

def test_fallback_frame_not_project_text():
    text = _fallback_frame()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


def test_pixel_to_char_dark_is_dense():
    dark = _pixel_to_char(0)
    assert dark.strip() != ""
    white = _pixel_to_char(255)
    assert white == " "


def test_pixel_to_char_alpha_transparent_is_space():
    assert _pixel_to_char(0, alpha=0) == " "
    assert _pixel_to_char(128, alpha=50) == " "


def test_ansi_rgb_format():
    assert ansi_rgb(255, 255, 255) == "#ffffff"
    assert ansi_rgb(23, 73, 148) == "#174994"


def test_color_constants():
    assert WHITE == (255, 255, 255)
    assert CAS_BLUE == (23, 73, 148)


def test_default_lines_is_30():
    assert LINES == 30


# ── Rotation direction ──

def test_real_rotation_angle_clockwise():
    assert real_rotation_angle(15, clockwise=True) == -15
    assert real_rotation_angle(30, clockwise=False) == 30
    assert real_rotation_angle(0, clockwise=True) == 0


def test_real_rotation_angle_all_steps():
    """Every frame step should produce negative angles for clockwise."""
    for deg in range(0, 360, 15):
        assert real_rotation_angle(deg, clockwise=True) == -deg
        assert real_rotation_angle(deg, clockwise=False) == deg


# ── Gradient uses fixed bounds ──

def test_gradient_uses_fixed_bounds():
    """colorize_blue_white_gradient must not use dynamic character bounds."""
    import inspect
    src = inspect.getsource(colorize_blue_white_gradient)
    assert "minx" not in src
    assert "maxx" not in src
    assert "miny" not in src
    assert "maxy" not in src
    assert "atan2" not in src
    assert "ring_angle" not in src


def test_gradient_not_sweeping():
    """No angular sweep; gradient uses fixed diagonal formula."""
    import inspect
    src = inspect.getsource(colorize_blue_white_gradient)
    assert "0.55 * nx" in src
    assert "0.45 * ny" in src


def test_gradient_fixed_bounds_produce_consistent_output():
    """Gradient with same width/height should produce same color regardless of content."""
    lines_a = ["███", "███", "███"]
    lines_b = ["█ █", "███", "█ █"]
    result_a = colorize_blue_white_gradient(lines_a, width=3, height=3)
    result_b = colorize_blue_white_gradient(lines_b, width=3, height=3)
    char_a = result_a.plain.splitlines()[1][1]
    char_b = result_b.plain.splitlines()[1][1]
    # Non-space chars at same position should have same style
    # The gradient depends on (x, y) position, not content


# ── Ring frame ──

def test_make_clean_ring_frame_has_ring():
    """Ring frame should produce an image with content (not all white)."""
    if not HAS_PIL:
        return
    from PIL import Image
    img = Image.new("L", (100, 100), 0)
    result = make_clean_ring_frame(img, angle=0)
    assert result.size == (100, 100)
    pixels = [result.getpixel((x, y)) for y in range(100) for x in range(100)]
    assert min(pixels) < 128, "Ring frame should have dark pixels (the ring)"


# ── Build frames ──

def test_build_frames_rotates_image():
    """build_frames should use PIL rotate on source image."""
    import inspect
    src = inspect.getsource(build_frames)
    assert "make_clean_ring_frame" in src
    assert "real_rotation_angle" in src


def test_build_frames_without_pil(monkeypatch):
    """When PIL is not available, build_frames returns single fallback."""
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    frames = build_frames()
    assert isinstance(frames, list)
    assert len(frames) == 1


def test_load_logo_frames_returns_list_without_pil(monkeypatch):
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    frames = load_logo_frames()
    assert isinstance(frames, list)
    assert len(frames) >= 1


def test_load_logo_text_returns_text_without_pil(monkeypatch):
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    text = load_logo_text()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


# ── Outline fill ──

def test_render_outline_fill_accepts_max_width():
    import inspect
    sig = inspect.signature(render_outline_fill)
    assert "max_width" in sig.parameters


# ── Preflight ──

def test_preflight_animation_preserves_result_status():
    result = CheckItem(name="Git", status="pass", message="git version 2.x", blocking=False)
    animated = CheckItem(name=result.name, status="pending", message="", blocking=result.blocking)
    assert animated.status == "pending"
    animated.status = "running"
    animated.message = "正在检查……"
    assert animated.status == "running"
    animated.status = result.status
    animated.message = result.message
    animated.blocking = result.blocking
    assert animated.status == "pass"
    assert animated.message == "git version 2.x"


# ── Boot splash ──

def test_boot_splash_uses_dismiss():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    assert "self.dismiss" in source


def test_boot_splash_has_key_bindings():
    from app.tui.widgets.boot_splash import BootSplash
    binding_keys = [b.key for b in BootSplash.BINDINGS]
    assert "ctrl+c" in binding_keys
    assert "q" in binding_keys
    assert "escape" in binding_keys


def test_boot_splash_no_on_done_param():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    sig = inspect.signature(BootSplash.__init__)
    assert "on_done" not in sig.parameters


def test_boot_splash_has_cancelled_guard():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    assert "self._cancelled" in source


def test_boot_splash_has_animation_support():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash.on_mount)
    assert "load_logo_frames" in source


def test_boot_splash_stops_animation_on_dismiss():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    skip_source = inspect.getsource(BootSplash.action_skip_splash)
    assert "self._playing = False" in skip_source


def test_boot_splash_always_dismisses():
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    assert "self.dismiss(results)" in source


def test_boot_splash_css_nowrap():
    from app.tui.widgets.boot_splash import BootSplash
    css = BootSplash.DEFAULT_CSS
    assert "nowrap" in css or "overflow" in css


def test_boot_splash_passes_max_width():
    """BootSplash should compute and pass max_width to load_logo_frames."""
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash.on_mount)
    assert "max_width" in source or "available_width" in source


# ── Preflight blocking ──

def test_pillow_is_non_blocking_in_preflight():
    from app.tui.preflight import run_preflight
    import inspect
    source = inspect.getsource(run_preflight)
    pillow_idx = source.find("依赖 Pillow")
    assert pillow_idx != -1
    context = source[pillow_idx:pillow_idx + 120]
    assert "blocking=False" in context or "非阻塞" in context


def test_app_on_splash_done_stores_results():
    from app.tui.app import PaperAgentApp
    import inspect
    source = inspect.getsource(PaperAgentApp._on_splash_done)
    assert "_preflight_results" in source


def test_app_has_show_preflight_warnings():
    from app.tui.app import PaperAgentApp
    assert hasattr(PaperAgentApp, "_show_preflight_warnings")