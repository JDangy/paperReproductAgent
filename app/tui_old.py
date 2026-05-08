from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
import shlex
import subprocess
from typing import Callable, Optional

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

from app.agents.input_resolver_agent import InputResolverAgent, PaperInputResolution
from app.core.file_utils import load_state
from app.core.progress import ProgressEvent, progress_events
from app.core.state import TaskState


PipelineRunner = Callable[..., TaskState]


# ---------------------------------------------------------------------------
# Theme – OpenCode-inspired Dracula palette
# ---------------------------------------------------------------------------

class _T:
    """Centralised colour palette."""

    GREEN = "#50fa7b"
    PURPLE = "#bd93f9"
    BLUE = "#8be9fd"
    RED = "#ff5555"
    ORANGE = "#ffb86c"
    YELLOW = "#f1fa8c"
    PINK = "#ff79c6"

    FG = "#cdd6f4"
    FG_DIM = "#6c7086"
    FG_MUTED = "#585b70"

    BG = "#1e1e2e"
    BG_STATUS = "#313244"


# ---------------------------------------------------------------------------
# Timeline entry (for structured rendering)
# ---------------------------------------------------------------------------

@dataclass
class TimelineEntry:
    """Structured message for panel rendering."""
    stage: str
    message: str
    level: str = "info"
    detail: str | None = None
    timestamp: float = 0.0

    def border_color(self) -> str:
        if self.stage == "User":
            return _T.GREEN
        if self.level == "error":
            return _T.RED
        if self.level == "success":
            return _T.GREEN
        if self.level == "warning":
            return _T.ORANGE
        if self.stage in ("Agent", "Help", "System"):
            return _T.PURPLE
        return _T.FG_MUTED


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLASH_COMMANDS = {
    "help",
    "submit",
    "new",
    "sessions",
    "select",
    "input",
    "repo",
    "repo-dir",
    "backend",
    "workspace",
    "timeout",
    "repairs",
    "run",
    "status",
    "report",
    "logs",
    "quit",
    "exit",
}


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

@dataclass
class TuiSession:
    name: str
    input_value: str | None = None
    repo: str | None = None
    repo_dir: str | None = None
    backend: str = "conda"
    workspace: str = "./workspace"
    timeout_minutes: int = 30
    max_repair_attempts: int = 5
    task_dir: str | None = None
    status: str = "draft"
    report_path: str | None = None
    input_resolved: bool = False
    input_resolution: str | None = None
    timeline: list[str] = field(default_factory=list)
    entries: list[TimelineEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Command parser
# ---------------------------------------------------------------------------

def parse_command(line: str) -> tuple[str, str]:
    stripped = line.strip()
    if not stripped:
        return "", ""
    if stripped.startswith("!"):
        return "!", stripped[1:].strip()
    if not stripped.startswith("/"):
        return "message", stripped
    parts = stripped[1:].split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if command not in SLASH_COMMANDS:
        return "message", stripped
    return command, args


# ---------------------------------------------------------------------------
# Main TUI class
# ---------------------------------------------------------------------------

class PaperSmokeTUI:

    def __init__(
        self,
        runner: PipelineRunner,
        *,
        workspace: str,
        backend: str,
        timeout_minutes: int,
        max_repair_attempts: int,
        console: Console | None = None,
        resolver: InputResolverAgent | None = None,
    ):
        self.runner = runner
        self.console = console or Console()
        self.resolver = resolver or InputResolverAgent()
        self.sessions: list[TuiSession] = [
            TuiSession(
                name="session-1",
                workspace=workspace,
                backend=backend,
                timeout_minutes=timeout_minutes,
                max_repair_attempts=max_repair_attempts,
            )
        ]
        self.active_index = 0
        self.running = True
        self.agent_running = False
        self._live: Live | None = None

    @property
    def active(self) -> TuiSession:
        return self.sessions[self.active_index]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Trigger a refresh (used during pipeline progress)."""
        if self._live is not None and self._live.is_started:
            self._live.refresh()
        elif not self.console.is_terminal:
            self._render_plain()

    def _render_plain(self) -> None:
        """Fallback rendering for non-terminal mode (piped stdin)."""
        self.console.clear()
        self.console.print(self._build_renderable())

    def _build_renderable(self) -> RenderableType:
        """Compose the full screen layout for Live display."""
        h = self.console.size.height
        w = self.console.size.width

        title_h = 3
        sep_h = 1
        input_h = 3
        status_h = 1
        msg_h = max(5, h - title_h - sep_h - input_h - status_h)

        return Group(
            self._render_title_bar(),
            self._render_messages(msg_h, w),
            Rule(style=_T.FG_DIM),
            self._render_input_area(w),
            self._render_status_bar(w),
        )

    def _render_title_bar(self) -> Panel:
        session = self.active
        status_text = "运行中" if self.agent_running else session.status
        status_color = _T.GREEN if status_text in ("success", "运行中") else _T.ORANGE

        title = Text.assemble(
            Text("论文复现冒烟测试", style=f"bold {_T.GREEN}"),
            Text("  "),
            Text(session.name, style=_T.FG_DIM),
            Text("  "),
            Text(f"后端={session.backend}", style=_T.FG_DIM),
            Text("  "),
            Text(f"状态={status_text}", style=f"bold {status_color}"),
        )

        if self.agent_running:
            running_indicator = Text("  \u23f3 运行中...", style=f"bold {_T.GREEN}")
            return Panel(Text.assemble(title, running_indicator), padding=(0, 1))

        return Panel(title, padding=(0, 1))

    def _render_messages(self, height: int, width: int) -> Panel:
        entries = self.active.entries
        if not entries:
            return Panel(Text("暂无事件。", style="dim"), padding=(0, 1))

        usable = height - 2  # panel padding
        rendered: list[RenderableType] = []
        count = 0
        for entry in reversed(entries):
            rendered.insert(0, self._render_entry(entry, width - 4))
            count += 2 if entry.detail else 1
            if count >= usable:
                break

        return Panel(Group(*rendered), padding=(0, 1))

    def _render_entry(self, entry: TimelineEntry, width: int) -> RenderableType:
        color = entry.border_color()
        bar = Text("\u2503 ", style=f"bold {color}")
        stage_label = Text(f"{entry.stage:<12}", style=f"bold {color}")
        msg_text = Text(entry.message)

        line1 = Text.assemble(bar, stage_label, Text(" "), msg_text)
        if entry.detail:
            detail_line = Text.assemble(
                Text("\u2503 ", style=f"bold {color}"),
                Text(f"  {entry.detail}", style="dim"),
            )
            return Group(line1, detail_line)
        return line1

    def _render_input_area(self, width: int) -> Panel:
        if self.agent_running:
            content = Text.assemble(
                Text("> ", style=f"bold {_T.FG_DIM}"),
                Text("Agent 运行中，输入已禁用", style=_T.ORANGE),
            )
        else:
            content = Text.assemble(
                Text("> ", style=f"bold {_T.GREEN}"),
                Text("输入本地 PDF 路径或 /help 查看帮助", style=_T.FG_DIM),
            )
        return Panel(content, padding=(0, 1))

    def _render_status_bar(self, width: int) -> Text:
        session = self.active
        task = _short(session.task_dir, 25)
        report = _short(session.report_path, 25)
        status_color = _T.GREEN if session.status == "success" else _T.ORANGE

        return Text.assemble(
            Text(" 帮助 ", style=f"bold white on {_T.BLUE}"),
            Text(" "),
            Text(f" {session.name} ", style=_T.FG_DIM),
            Text(" "),
            Text(f" {session.backend} ", style=f"bold {_T.BLUE}"),
            Text(" "),
            Text(f" {session.status} ", style=f"bold {status_color}"),
            Text("   "),
            Text(f"任务:{task}", style=_T.FG_DIM),
            Text("  "),
            Text(f"报告:{report}", style=_T.FG_DIM),
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._append("Agent", "把要复现的本地论文 PDF 路径发给我就行，例如 @/path/to/paper.pdf。")

        use_live = self.console.is_terminal
        if use_live:
            self._live = Live(
                get_renderable=self._build_renderable,
                console=self.console,
                screen=True,
                auto_refresh=True,
                refresh_per_second=4,
            )
            self._live.start()

        try:
            while self.running:
                if use_live:
                    self._live.stop()
                else:
                    self._render_plain()
                try:
                    line = Prompt.ask("[bold cyan]>[/bold cyan]", console=self.console)
                except (EOFError, KeyboardInterrupt):
                    self.running = False
                    break
                if use_live:
                    self._live.start()
                self.handle_line(line)
        finally:
            if use_live and self._live.is_started:
                self._live.stop()

        self.console.print("[green]再见。[/green]")

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.agent_running:
            self._append("System", "Agent 正在运行，暂不接受新的输入。", level="warning")
            return

        command, args = parse_command(line)
        if command == "":
            return
        if command == "!":
            self._run_shell(args)
            return
        if command == "message":
            self._submit_paper(args)
            return

        handlers = {
            "help": self._cmd_help,
            "submit": self._cmd_submit,
            "new": self._cmd_new,
            "sessions": self._cmd_sessions,
            "select": self._cmd_select,
            "input": self._cmd_input,
            "repo": self._cmd_repo,
            "repo-dir": self._cmd_repo_dir,
            "backend": self._cmd_backend,
            "workspace": self._cmd_workspace,
            "timeout": self._cmd_timeout,
            "repairs": self._cmd_repairs,
            "run": self._cmd_run,
            "status": self._cmd_status,
            "report": self._cmd_report,
            "logs": self._cmd_logs,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
        }
        handler = handlers.get(command)
        if handler is None:
            self._append("System", f"未知命令：/{command}", level="warning")
            return
        handler(args)

    # ------------------------------------------------------------------
    # Command handlers (logic unchanged)
    # ------------------------------------------------------------------

    def _cmd_help(self, _: str) -> None:
        self._append("Help", "直接输入本地论文 PDF 路径即可开始复现。")
        self._append("Help", "命令：/new [名称], /select N, /input 路径, /submit 路径, /repo URL, /repo-dir 路径")
        self._append("Help", "运行：/backend conda|venv|docker|local|none, /timeout 分钟数, /repairs 次数, /run")
        self._append("Help", "查看：/status, /logs env|build|smoke|stderr|stdout, /report, !shell命令")

    def _cmd_new(self, args: str) -> None:
        name = args.strip() or f"session-{len(self.sessions) + 1}"
        current = self.active
        self.sessions.append(
            TuiSession(
                name=name,
                workspace=current.workspace,
                backend=current.backend,
                timeout_minutes=current.timeout_minutes,
                max_repair_attempts=current.max_repair_attempts,
            )
        )
        self.active_index = len(self.sessions) - 1
        self._append("System", f"已创建会话 {name}")

    def _cmd_sessions(self, _: str) -> None:
        for idx, session in enumerate(self.sessions, start=1):
            self._append("Sessions", f"{idx}. {session.name} [{session.status}]")

    def _cmd_select(self, args: str) -> None:
        try:
            index = int(args.strip()) - 1
        except ValueError:
            self._append("System", "用法：/select N", level="warning")
            return
        if not 0 <= index < len(self.sessions):
            self._append("System", f"会话序号超出范围：{index + 1}", level="warning")
            return
        self.active_index = index
        self._append("System", f"已切换到 {self.active.name}")

    def _cmd_input(self, args: str) -> None:
        self.active.input_value = _strip_at(args)
        self.active.input_resolved = False
        self.active.input_resolution = None
        self._append("Config", f"input = {self.active.input_value}")

    def _cmd_submit(self, args: str) -> None:
        self._submit_paper(args)

    def _cmd_repo(self, args: str) -> None:
        self.active.repo = args.strip() or None
        self._append("Config", f"repo = {self.active.repo or '-'}")

    def _cmd_repo_dir(self, args: str) -> None:
        self.active.repo_dir = _strip_at(args)
        self._append("Config", f"repo_dir = {self.active.repo_dir}")

    def _cmd_backend(self, args: str) -> None:
        backend = args.strip()
        if backend not in {"none", "local", "venv", "conda", "docker"}:
            self._append("Config", "后端必须是：none、local、venv、conda 或 docker", level="warning")
            return
        self.active.backend = backend
        self._append("Config", f"backend = {backend}")

    def _cmd_workspace(self, args: str) -> None:
        self.active.workspace = args.strip() or self.active.workspace
        self._append("Config", f"workspace = {self.active.workspace}")

    def _cmd_timeout(self, args: str) -> None:
        try:
            self.active.timeout_minutes = int(args.strip())
            self._append("Config", f"timeout = {self.active.timeout_minutes}")
        except ValueError:
            self._append("Config", "用法：/timeout 分钟数", level="warning")

    def _cmd_repairs(self, args: str) -> None:
        try:
            self.active.max_repair_attempts = int(args.strip())
            self._append("Config", f"repairs = {self.active.max_repair_attempts}")
        except ValueError:
            self._append("Config", "用法：/repairs 次数", level="warning")

    def _cmd_run(self, _: str) -> None:
        session = self.active
        if not session.input_value:
            self._append("Agent", "先把本地论文 PDF 路径发给我，例如 @/path/to/paper.pdf。", level="warning")
            return

        self.agent_running = True

        try:
            if not session.input_resolved and not self._resolve_active_input():
                return

            session.status = "running"
            self._append("Agent", "开始复现流水线。")

            def on_progress(event: ProgressEvent) -> None:
                self._append(event.stage, event.message, level=event.level, detail=event.detail)
                self.render()

            with progress_events(on_progress):
                state = self.runner(
                    input_value=session.input_value,
                    workspace=session.workspace,
                    backend=session.backend,
                    repo=session.repo,
                    repo_dir=session.repo_dir,
                    timeout_minutes=session.timeout_minutes,
                    max_repair_attempts=session.max_repair_attempts,
                )
        except Exception as e:
            session.status = "failed"
            self._append("Run", f"流水线异常退出：{e}", level="error")
            return
        finally:
            self.agent_running = False

        session.task_dir = state.task_dir
        session.status = state.report.final_status if state.report else state.status
        report_path = Path(state.task_dir) / "report" / "reproduction_smoke_report.md"
        session.report_path = str(report_path) if report_path.exists() else None
        self._append("Run", f"已完成：{session.status}", level="success")
        self._append_final_report(report_path)

    def _cmd_status(self, _: str) -> None:
        session = self.active
        if not session.task_dir:
            self._append("Status", "当前会话尚未运行过任务。")
            return
        try:
            state = load_state(session.task_dir)
        except Exception as e:
            self._append("Status", f"无法加载状态：{e}", level="error")
            return
        self._append("Status", f"任务={state.task_id} 状态={state.status}")
        if state.report:
            self._append("Status", f"最终结果={state.report.final_status}")

    def _cmd_report(self, _: str) -> None:
        path = self._report_path()
        if path is None:
            self._append("Report", "报告暂不可用。", level="warning")
            return
        self._append("Report", str(path))
        self._append("Report", path.read_text(encoding="utf-8")[:2500])

    def _cmd_logs(self, args: str) -> None:
        session = self.active
        if not session.task_dir:
            self._append("Logs", "当前会话尚未运行过任务。", level="warning")
            return
        kind = args.strip() or "smoke"
        candidates = {
            "env": Path(session.task_dir) / "env" / "conda_build.log",
            "conda": Path(session.task_dir) / "env" / "conda_build.log",
            "venv": Path(session.task_dir) / "env" / "venv_build.log",
            "build": Path(session.task_dir) / "env" / "build.log",
            "smoke": Path(session.task_dir) / "runs" / "smoke_001" / "run_summary.json",
            "stderr": Path(session.task_dir) / "runs" / "smoke_001" / "stderr.log",
            "stdout": Path(session.task_dir) / "runs" / "smoke_001" / "stdout.log",
        }
        path = candidates.get(kind)
        if path is None:
            self._append("Logs", "用法：/logs env|build|smoke|stderr|stdout", level="warning")
            return
        if not path.exists():
            self._append("Logs", f"未找到：{path}", level="warning")
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        self._append("Logs", str(path))
        self._append("Logs", text[-3000:] if len(text) > 3000 else text)

    def _cmd_quit(self, _: str) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_shell(self, command: str) -> None:
        if not command:
            self._append("Shell", "用法：!命令", level="warning")
            return
        self._append("Shell", f"$ {command}")
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        except Exception as e:
            self._append("Shell", str(e), level="error")
            return
        output = (proc.stdout + proc.stderr).strip()
        self._append("Shell", output[-3000:] if output else f"exit {proc.returncode}")

    def _report_path(self) -> Path | None:
        if self.active.report_path:
            path = Path(self.active.report_path)
            if path.exists():
                return path
        if self.active.task_dir:
            path = Path(self.active.task_dir) / "report" / "reproduction_smoke_report.md"
            if path.exists():
                return path
        return None

    def _submit_paper(self, value: str) -> None:
        paper_input = _strip_at(value)
        if not paper_input:
            self._append("Agent", "请输入本地论文 PDF 路径。", level="warning")
            return
        self.active.input_value = paper_input
        self.active.input_resolved = False
        self.active.input_resolution = None
        self._append("User", paper_input)
        self._append("Agent", "收到。我先确认这个本地 PDF 是否可读取。")
        self._cmd_run("")

    def _resolve_active_input(self) -> bool:
        session = self.active
        self._append("Agent", "正在解析输入并确认本地 PDF 文件。")
        try:
            resolution = self.resolver.resolve(session.input_value or "")
        except Exception as e:
            session.status = "input_failed"
            self._append("Agent", f"输入解析失败：{e}", level="error")
            return False

        self._append_resolution(resolution)
        if not resolution.success or not resolution.input_value:
            session.status = "input_failed"
            return False

        session.input_value = resolution.input_value
        session.input_resolved = True
        session.input_resolution = resolution.reason
        return True

    def _append_resolution(self, resolution: PaperInputResolution) -> None:
        if resolution.success:
            parts = ["本地 PDF 已确认" if resolution.exists else "输入格式已确认"]
            if resolution.title:
                parts.append(f"标题：{resolution.title}")
            self._append("Agent", "；".join(parts), level="success")
            if resolution.reason:
                self._append("Agent", resolution.reason)
            return

        reason = resolution.failure_reason or resolution.reason or "无法把输入解析成可运行论文。"
        self._append("Agent", f"不能开始复现：{reason}", level="error")

    def _append_final_report(self, report_path: Path) -> None:
        if not report_path.exists():
            self._append("Report", f"未找到报告：{report_path}", level="warning")
            return
        self.active.report_path = str(report_path)
        self._append("Report", f"路径：{report_path}", level="success")
        text = report_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            self._append("Report", "报告文件为空", level="warning")
            return
        preview = text[:4000]
        if len(text) > len(preview):
            preview += "\n\n...[已截断；使用 /report 查看完整报告]"
        self._append("Report", preview)

    def _append(self, stage: str, message: str, *, level: str = "info", detail: str | None = None) -> None:
        # Structured entry for rendering
        entry = TimelineEntry(
            stage=stage,
            message=message,
            level=level,
            detail=detail,
            timestamp=time.time(),
        )
        self.active.entries.append(entry)
        # Raw markup string for backward compatibility with tests
        color = {
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        }.get(level, "white")
        if stage == "User":
            line = f"[bold]>[/bold] {escape(str(message))}"
        else:
            line = f"[{color}]{escape(stage):<12}[/{color}] {escape(str(message))}"
        if detail:
            line += f"\n[dim]  {escape(str(detail))}[/dim]"
        self.active.timeline.append(line)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tui(
    runner: PipelineRunner,
    *,
    workspace: str,
    backend: str,
    timeout_minutes: int,
    max_repair_attempts: int,
) -> None:
    PaperSmokeTUI(
        runner,
        workspace=workspace,
        backend=backend,
        timeout_minutes=timeout_minutes,
        max_repair_attempts=max_repair_attempts,
    ).run()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _short(value: Optional[str], limit: int = 36) -> str:
    if not value:
        return "-"
    if len(value) <= limit:
        return value
    return "..." + value[-(limit - 3):]


def _strip_at(value: str) -> str:
    stripped = value.strip()
    return stripped[1:] if stripped.startswith("@") else stripped
