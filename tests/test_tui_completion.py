from __future__ import annotations

"""Tests for app/tui/completion.py"""

from app.tui.completion import (
    complete_command,
    CompletionItem,
    normalize_query,
    fuzzy_subsequence_score,
)


def test_complete_slash_returns_commands():
    items = complete_command("/")
    assert len(items) > 0
    assert any(i.command == "run" for i in items)
    assert any(i.command == "report" for i in items)


def test_prefix_exit():
    items = complete_command("/e")
    assert any(i.command == "exit" for i in items)


def test_prefix_backend():
    items = complete_command("/back")
    assert len(items) > 0
    assert items[0].command == "backend"


def test_fuzzy_repo_dir():
    items = complete_command("/rd")
    assert any(i.command == "repo-dir" for i in items)


def test_fuzzy_open_report():
    items = complete_command("/or")
    assert any(i.command == "open-report" for i in items)


def test_fuzzy_artifact():
    items = complete_command("/art")
    assert any(i.command == "artifact" for i in items)


def test_no_completion_for_plain_text():
    items = complete_command("C:/paper.pdf")
    assert items == []


def test_no_completion_for_empty():
    items = complete_command("")
    assert items == []


def test_limit():
    # Limit applies when there's a query; empty / returns all
    assert len(complete_command("/s", limit=2)) <= 2


def test_case_insensitive():
    assert any(i.command == "run" for i in complete_command("/RUN"))


def test_completion_item_insert_text():
    item = CompletionItem(command="run", args="", description="", category="Run")
    assert item.insert_text == "/run"

    item2 = CompletionItem(command="backend", args="[none|...]", description="", category="Run")
    assert item2.insert_text == "/backend"


def test_normalize_query():
    assert normalize_query("heLlo") == "hello"
    assert normalize_query("/back-end_test") == "backendtest"
    assert normalize_query("repo-dir") == "repodir"
    assert normalize_query("  /PANEL  ") == "panel"


def test_fuzzy_subsequence_score_exact():
    score = fuzzy_subsequence_score("run", "run")
    assert score is not None
    assert score == 0


def test_fuzzy_subsequence_score_gap():
    score = fuzzy_subsequence_score("rd", "repo-dir")
    assert score is not None
    # Should match: r...p...o...-...d...i...r
    # r matches first, d matches later with gaps


def test_fuzzy_subsequence_score_no_match():
    score = fuzzy_subsequence_score("xyz", "backend")
    assert score is None
