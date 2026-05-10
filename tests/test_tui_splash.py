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
    FILL_CHARS,
    OUTLINE_CHARS,
    real_rotation_angle,
    LINES,
    render_outline_fill,
    colorize_blue_white_gradient,
)
from app.tui.preflight import CheckItem


def test_fallback_frame_not_project_text():
    text = _fallback_frame()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


def test_pixel_to_char_dark_is_dense():
    dark = _pixel_to_char(0)
    assert dark.strip() != "", f"Dark pixel mapped to space/blank: {dark!r}"
    white = _pixel_to_char(255)
    assert white == " ", f"White pixel should map to space, got: {white!r}"


def test_pixel_to_char_alpha_transparent_is_space():
    assert _pixel_to_char(0, alpha=0) == " "
    assert _pixel_to_char(128, alpha=50) == " "


def test_pixel_to_char_gradient():
    very_dark = _pixel_to_char(30)
    mid = _pixel_to_char(128)
    white = _pixel_to_char(255)
    assert very_dark.strip() != ""
    assert white == " "
    CHARS = " .:-=+*#%@"
    assert very_dark in CHARS
    assert mid in CHARS


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


def test_load_logo_text_returns_text_without_pil(monkeypatch):
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    text = load_logo_text()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


def test_load_logo_frames_returns_list_without_pil(monkeypatch):
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    frames = load_logo_frames()
    assert isinstance(frames, list)
    assert len(frames) >= 1


def test_ansi_rgb_format():
    assert ansi_rgb(255, 255, 255) == "#ffffff"
    assert ansi_rgb(23, 73, 148) == "#174994"
    assert ansi_rgb(0, 0, 0) == "#000000"


def test_color_constants():
    assert WHITE == (255, 255, 255)
    assert CAS_BLUE == (23, 73, 148)


def test_char_sets_not_empty():
    assert len(FILL_CHARS) > 0
    assert len(OUTLINE_CHARS) > 0


def test_real_rotation_angle_clockwise():
    assert real_rotation_angle(15, clockwise=True) == -15
    assert real_rotation_angle(30, clockwise=False) == 30
    assert real_rotation_angle(0, clockwise=True) == 0


def test_default_lines_is_30():
    assert LINES == 30


def test_colorize_uses_fixed_bounds():
    """colorize_blue_white_gradient uses width/height params, not live content bounds."""
    import inspect
    src = inspect.getsource(colorize_blue_white_gradient)
    assert "width" in src
    assert "height" in src
    assert "minx" not in src
    assert "maxx" not in src


def test_gradient_not_sweeping():
    """Gradient should use fixed bounds, not atan2 per-pixel angle sweep."""
    import inspect
    src = inspect.getsource(colorize_blue_white_gradient)
    assert "atan2" not in src
    assert "ring_angle" not in src


def test_build_frames_rotates_image():
    """build_frames should use PIL rotate, not color sweep."""
    import inspect
    from app.tui.logo_loader import build_frames
    src = inspect.getsource(build_frames)
    assert "rotate" in src
    assert "real_rotation_angle" in src


def test_render_outline_fill_accepts_max_width():
    """render_outline_fill should accept max_width parameter."""
    import inspect
    sig = inspect.signature(render_outline_fill)
    assert "max_width" in sig.parameters


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
    """Splash logo CSS should include nowrap/overflow to prevent wrapping."""
    from app.tui.widgets.boot_splash import BootSplash
    css = BootSplash.DEFAULT_CSS
    assert "nowrap" in css or "overflow" in css


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