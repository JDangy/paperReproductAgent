from __future__ import annotations

"""Tests for TUI command parsing."""

from app.tui.app import parse_command


def test_parse_pdf_input():
    cmd, args = parse_command("@/path/to/paper.pdf")
    assert cmd == "message"
    assert "/path/to/paper.pdf" in args


def test_parse_slash_command():
    cmd, args = parse_command("/run")
    assert cmd == "run"
    assert args == ""


def test_parse_slash_command_with_args():
    cmd, args = parse_command("/backend conda")
    assert cmd == "backend"
    assert args == "conda"


def test_parse_unknown_slash_falls_back_to_message():
    cmd, args = parse_command("/unknown blah")
    assert cmd == "message"
    assert "/unknown blah" in args


def test_parse_shell_bang():
    cmd, args = parse_command("!ls -la")
    assert cmd == "!"
    assert args == "ls -la"


def test_parse_empty():
    cmd, args = parse_command("")
    assert cmd == ""


def test_parse_whitespace_only():
    cmd, args = parse_command("   ")
    assert cmd == ""


def test_parse_help_command():
    cmd, args = parse_command("/help")
    assert cmd == "help"


def test_parse_panel_command():
    cmd, args = parse_command("/panel help")
    assert cmd == "panel"
    assert args == "help"


def test_parse_logs_command():
    cmd, args = parse_command("/logs smoke")
    assert cmd == "logs"
    assert args == "smoke"
