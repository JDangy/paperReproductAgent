from __future__ import annotations

"""Tests for app/tui/logo.py"""

from app.tui.logo import build_logo_lines, render_logo, render_compact_logo, gradient_text


def test_build_logo_lines_returns_nonempty():
    lines = build_logo_lines()
    assert len(lines) > 0
    assert any(line.strip() for line in lines)


def test_render_logo_narrow_falls_back_to_compact():
    texts = render_logo(max_width=40)
    assert len(texts) == 1
    assert "Paper" in str(texts[0])


def test_render_logo_wide_returns_full():
    texts = render_logo(max_width=200)
    assert len(texts) > 1


def test_render_compact_logo_returns_text():
    text = render_compact_logo()
    assert "Paper" in str(text)
    assert "Reproduct" in str(text)
    assert "Agent" in str(text)


def test_gradient_text_returns_rich_text():
    line = "██████╗"
    result = gradient_text(line, 80)
    from rich.text import Text
    assert isinstance(result, Text)


def test_gradient_text_empty_line():
    result = gradient_text("", 80)
    from rich.text import Text
    assert isinstance(result, Text)


def test_no_raw_ansi_escapes():
    lines = build_logo_lines()
    for line in lines:
        assert "\033[" not in line
        assert "\x1b[" not in line


def test_render_logo_default_no_max_width():
    texts = render_logo()
    assert len(texts) > 1
