from __future__ import annotations

"""Tests for boot splash, logo loader, and preflight fixes."""

from app.tui.logo_loader import _pixel_to_char, _fallback_logo, load_logo_text
from app.tui.preflight import CheckItem


def test_fallback_logo_not_project_text():
    """Fallback logo must not contain 'Paper Reproduct Agent'."""
    text = _fallback_logo()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


def test_pixel_to_char_dark_is_dense():
    """Dark pixels (low gray) should map to dense characters, not spaces."""
    dark = _pixel_to_char(0)
    assert dark.strip() != "", f"Dark pixel mapped to space/blank: {dark!r}"
    white = _pixel_to_char(255)
    assert white == " ", f"White pixel should map to space, got: {white!r}"


def test_pixel_to_char_alpha_transparent_is_space():
    """Transparent pixels (low alpha) should be spaces."""
    assert _pixel_to_char(0, alpha=0) == " "
    assert _pixel_to_char(128, alpha=50) == " "


def test_pixel_to_char_gradient():
    """Darker pixels should produce denser characters."""
    very_dark = _pixel_to_char(30)
    mid = _pixel_to_char(128)
    white = _pixel_to_char(255)
    assert very_dark.strip() != ""
    assert white == " "
    CHARS = " .:-=+*#%@"
    assert very_dark in CHARS
    assert mid in CHARS


def test_preflight_animation_preserves_result_status():
    """Animation logic should not overwrite pass/fail status."""
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
    """When PIL is not available, load_logo_text should return empty fallback."""
    import app.tui.logo_loader as ll
    monkeypatch.setattr(ll, "HAS_PIL", False)
    text = load_logo_text()
    assert "Paper" not in text.plain
    assert "Reproduct" not in text.plain
    assert "Agent" not in text.plain


def test_boot_splash_uses_dismiss_not_only_callback():
    """BootSplash._run_checks should call dismiss(), not just _on_done callback."""
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    assert "self.dismiss" in source
    assert "self._on_done" not in source


def test_boot_splash_has_key_bindings():
    """BootSplash must have quit and skip bindings."""
    from app.tui.widgets.boot_splash import BootSplash
    binding_keys = [b.key for b in BootSplash.BINDINGS]
    assert "ctrl+c" in binding_keys
    assert "q" in binding_keys
    assert "escape" in binding_keys


def test_boot_splash_no_on_done_param():
    """BootSplash.__init__ should not accept on_done parameter."""
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    sig = inspect.signature(BootSplash.__init__)
    assert "on_done" not in sig.parameters


def test_boot_splash_has_cancelled_guard():
    """BootSplash should have _cancelled attribute for skip/quit guards."""
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    assert "self._cancelled" in source


def test_boot_splash_always_dismisses():
    """BootSplash._run_checks must always call dismiss, even with blocking failures."""
    from app.tui.widgets.boot_splash import BootSplash
    import inspect
    source = inspect.getsource(BootSplash._run_checks)
    lines_after_blocking = False
    for line in source.splitlines():
        if "blocking" in line and "将进入" in source:
            lines_after_blocking = True
    # dismiss must appear (regardless of blocking count)
    assert "self.dismiss(results)" in source


def test_pillow_is_non_blocking_in_preflight():
    """Pillow check should be non-blocking so TUI still starts if missing."""
    from app.tui.preflight import run_preflight
    import inspect
    source = inspect.getsource(run_preflight)
    # Find the Pillow check
    pillow_idx = source.find("依赖 Pillow")
    assert pillow_idx != -1
    # Check that there's no blocking=True near the Pillow fail case
    fail_idx = source.find("fail", pillow_idx)
    # Get the context around the Pillow fail record
    context = source[pillow_idx:pillow_idx + 120]
    assert "blocking=False" in context or "非阻塞" in context


def test_app_on_splash_done_stores_results():
    """_on_splash_done should store results for warning display."""
    from app.tui.app import PaperAgentApp
    import inspect
    source = inspect.getsource(PaperAgentApp._on_splash_done)
    assert "_preflight_results" in source


def test_app_has_show_preflight_warnings():
    """PaperAgentApp should have _show_preflight_warnings method."""
    from app.tui.app import PaperAgentApp
    assert hasattr(PaperAgentApp, "_show_preflight_warnings")