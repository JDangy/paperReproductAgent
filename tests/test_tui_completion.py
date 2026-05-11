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


def test_prefix_exit_first():
    """prefix /ex should rank exit first"""
    items = complete_command("/ex")
    assert len(items) > 0
    assert items[0].command == "exit"


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


def test_command_descriptions_are_chinese():
    from app.tui.commands import COMMANDS
    assert COMMANDS["exit"].description == "退出 TUI"
    assert COMMANDS["backend"].description == "设置执行后端"
    assert COMMANDS["run"].description == "执行复现流水线"
    assert COMMANDS["exit"].category == "系统"
    assert COMMANDS["run"].category == "运行"


def test_help_text_no_rich_markup():
    """Build help text and verify no Rich markup leaks through."""
    from app.tui.app import _HELP_CATEGORIES
    from app.tui.commands import COMMANDS
    lines = ["## 可用命令", ""]
    for cat_name, cmds in _HELP_CATEGORIES.items():
        lines.append(f"### {cat_name}")
        for name in cmds:
            meta = COMMANDS[name]
            arg_str = f" {meta.display_args or meta.args}" if (meta.display_args or meta.args) else ""
            lines.append(f"- `/{name}{arg_str}` — {meta.description}")
        lines.append("")
    text = "\n".join(lines)
    assert "[bold" not in text
    assert "[/" not in text
    assert "可用命令" in text
    assert "输入" in text
    assert "运行" in text
    assert "/exit" in text


def test_completion_has_required_args():
    item = CompletionItem(command="timeout", args="<minutes>", description="设置超时", category="运行")
    assert item.has_required_args
    assert item.has_any_args

    item2 = CompletionItem(command="run", args="", description="执行流水线", category="运行")
    assert not item2.has_required_args
    assert not item2.has_any_args

    item3 = CompletionItem(command="backend", args="[none|...]", description="设置后端", category="运行")
    assert not item3.has_required_args
    assert item3.has_any_args


def test_completion_prefix_ex_is_first():
    items = complete_command("/ex")
    assert items[0].command == "exit"


def test_completion_prefix_ru_is_run():
    items = complete_command("/ru")
    assert items[0].command == "run"


def test_normalize_preserves_chinese():
    assert "退出" in normalize_query("退出")
    assert normalize_query("退出 TUI") == "退出tui"
