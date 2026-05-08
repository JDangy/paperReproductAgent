from __future__ import annotations

"""Slash command metadata for the TUI."""

from typing import NamedTuple


class CommandMeta(NamedTuple):
    name: str
    args: str  # empty = no args
    description: str
    category: str  # Input, Run, View, Mode, Session, System
    safe_during_run: bool = False  # allowed while pipeline is running


COMMANDS: dict[str, CommandMeta] = {
    "help": CommandMeta("help", "", "Show help", "System", True),
    "clear": CommandMeta("clear", "", "Clear message timeline", "System", True),
    "status": CommandMeta("status", "", "Show pipeline status", "View", True),
    "plan": CommandMeta("plan", "", "Switch to PLAN mode", "Mode", False),
    "act": CommandMeta("act", "", "Switch to ACT mode", "Mode", False),
    "input": CommandMeta("input", "<path>", "Set local PDF path", "Input", False),
    "repo": CommandMeta("repo", "<url>", "Set repo URL directly", "Input", False),
    "repo-dir": CommandMeta("repo-dir", "<path>", "Set local repo dir", "Input", False),
    "backend": CommandMeta("backend", "[none|local|venv|conda|docker]", "Set execution backend", "Run", False),
    "workspace": CommandMeta("workspace", "<path>", "Set output workspace", "Run", False),
    "timeout": CommandMeta("timeout", "<minutes>", "Set timeout", "Run", False),
    "repairs": CommandMeta("repairs", "<n>", "Set max repair attempts", "Run", False),
    "run": CommandMeta("run", "", "Execute pipeline", "Run", False),
    "report": CommandMeta("report", "", "Show report", "View", True),
    "logs": CommandMeta("logs", "<type>", "View logs", "View", True),
    "cancel": CommandMeta("cancel", "", "Cancel pipeline", "Run", True),
    "sessions": CommandMeta("sessions", "", "List saved sessions", "Session", True),
    "resume": CommandMeta("resume", "<session-id>", "Resume session", "Session", False),
    "quit": CommandMeta("quit", "", "Exit TUI", "System", True),
    "exit": CommandMeta("exit", "", "Exit TUI", "System", True),
    "panel": CommandMeta("panel", "[session|pipeline|help|artifacts|none]", "Switch panel", "Mode", True),
    "artifact": CommandMeta("artifact", "", "Show task artifacts", "View", True),
    "open-report": CommandMeta("open-report", "", "Print report path", "View", True),
    "mode": CommandMeta("mode", "", "Show current mode", "Mode", True),
    "reset": CommandMeta("reset", "", "Clear session inputs", "Session", False),
}

RUNNING_SAFE_COMMANDS: set[str] = {n for n, m in COMMANDS.items() if m.safe_during_run}
RUNNING_SAFE_COMMANDS.add("!")  # shell needs confirmation but is still allowed
