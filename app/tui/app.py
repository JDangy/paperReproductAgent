from __future__ import annotations

"""PaperAgentApp – Textual-based Claude Code-style TUI."""

import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Header, Static

from app.agents.input_resolver_agent import InputResolverAgent, PaperInputResolution
from app.core.file_utils import load_state
from app.core.progress import ProgressEvent, progress_events
from app.core.state import TaskState
from app.runtime.events import AgentEvent
from app.runtime.session import Session, SessionStore, make_progress_bridge

from .widgets import Composer, MessageTimeline, StatusBar, ToolCard
from . import theme as T

PipelineRunner = Callable[..., TaskState]


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

SLASH_COMMANDS = {
    "help",
    "clear",
    "status",
    "plan",
    "act",
    "input",
    "repo",
    "repo-dir",
    "backend",
    "workspace",
    "timeout",
    "repairs",
    "run",
    "report",
    "logs",
    "quit",
    "exit",
}


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
# Main App
# ---------------------------------------------------------------------------

class PaperAgentApp(App):
    """Claude Code-style TUI for paper reproduction agent."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-area {
        height: 1fr;
    }
    #title-bar {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
        content-align: left middle;
    }
    """

    TITLE = "论文复现冒烟测试"
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=True),
        Binding("ctrl+l", "clear_screen", "清屏", show=False),
        Binding("ctrl+p", "toggle_plan_mode", "计划模式", show=False),
    ]

    def __init__(
        self,
        runner: PipelineRunner,
        *,
        workspace: str,
        backend: str,
        timeout_minutes: int,
        max_repair_attempts: int,
        resolver: InputResolverAgent | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.runner = runner
        self.resolver = resolver or InputResolverAgent()
        self.session = Session(
            backend=backend,
            workspace=workspace,
            timeout_minutes=timeout_minutes,
            max_repair_attempts=max_repair_attempts,
        )
        self.store = SessionStore(self.session.id)
        self.agent_running = False
        self._timeline: MessageTimeline | None = None
        self._status_bar: StatusBar | None = None
        self._composer: Composer | None = None
        self._tool_cards: dict[str, ToolCard] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            f"  [bold {T.GREEN}]论文复现冒烟测试[/]  "
            f"[{T.FG_DIM}]session: {self.session.id}[/]",
            id="title-bar",
        )
        yield MessageTimeline(id="main-area")
        yield StatusBar()
        yield Composer()

    def on_mount(self) -> None:
        self._timeline = self.query_one(MessageTimeline)
        self._status_bar = self.query_one(StatusBar)
        self._composer = self.query_one(Composer)
        self._composer.focus_input()
        self._add_assistant("把要复现的本地论文 PDF 路径发给我就行，例如 @/path/to/paper.pdf。")
        self._update_status()

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def _add_assistant(self, text: str) -> None:
        if self._timeline:
            self._timeline.add_assistant(text)
        self.store.append(AgentEvent(type="assistant_message", payload={"text": text}))

    def _add_user(self, text: str) -> None:
        if self._timeline:
            self._timeline.add_user(text)
        self.store.append(AgentEvent(type="user_message", payload={"text": text}))

    def _add_error(self, text: str) -> None:
        if self._timeline:
            self._timeline.add_error(text)
        self.store.append(AgentEvent(type="error", payload={"text": text}))

    def _update_status(self) -> None:
        if self._status_bar:
            paper_name = "-"
            if self.session.paper_path:
                paper_name = Path(self.session.paper_path).name
            self._status_bar.update_info(
                mode=self.session.mode.upper(),
                session=f"session-{self.session.id[:4]}",
                backend=self.session.backend,
                status=self.session.status,
                paper=paper_name,
            )

    # ------------------------------------------------------------------
    # Tool card helpers
    # ------------------------------------------------------------------

    def _get_or_create_tool_card(self, stage: str, message: str) -> ToolCard:
        if stage in self._tool_cards:
            return self._tool_cards[stage]
        card = ToolCard(name=stage, status="running", message=message)
        if self._timeline:
            self._timeline.mount(card)
            self._timeline.scroll_end(animate=False)
        self._tool_cards[stage] = card
        return card

    def _update_tool_card(self, stage: str, status: str, detail: str | None = None, duration: float | None = None) -> None:
        if stage in self._tool_cards:
            self._tool_cards[stage].update(status=status, detail=detail, duration=duration)

    # ------------------------------------------------------------------
    # Composer input handler
    # ------------------------------------------------------------------

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        line = event.value
        if not line:
            return
        self.handle_line(line)

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def handle_line(self, line: str) -> None:
        if self.agent_running:
            self._add_assistant("Agent 正在运行，暂不接受新的输入。")
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
            "clear": self._cmd_clear,
            "status": self._cmd_status,
            "plan": self._cmd_plan,
            "act": self._cmd_act,
            "input": self._cmd_input,
            "repo": self._cmd_repo,
            "repo-dir": self._cmd_repo_dir,
            "backend": self._cmd_backend,
            "workspace": self._cmd_workspace,
            "timeout": self._cmd_timeout,
            "repairs": self._cmd_repairs,
            "run": self._cmd_run,
            "report": self._cmd_report,
            "logs": self._cmd_logs,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
        }
        handler = handlers.get(command)
        if handler is None:
            self._add_assistant(f"未知命令：/{command}")
            return
        handler(args)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_help(self, _: str) -> None:
        self._add_assistant(
            "直接输入本地论文 PDF 路径即可开始复现。\n"
            "命令：/help, /clear, /status, /plan, /act, /input 路径, /repo URL, /repo-dir 路径\n"
            "运行：/backend venv|docker|local|none, /timeout 分钟数, /repairs 次数, /run\n"
            "查看：/status, /logs env|build|smoke|stderr|stdout, /report, !shell命令"
        )

    def _cmd_clear(self, _: str) -> None:
        if self._timeline:
            self._timeline.clear_messages()

    def _cmd_status(self, _: str) -> None:
        s = self.session
        if not s.task_dir:
            self._add_assistant("当前会话尚未运行过任务。")
            return
        try:
            state = load_state(s.task_dir)
            self._add_assistant(f"任务={state.task_id} 状态={state.status}")
            if state.report:
                self._add_assistant(f"最终结果={state.report.final_status}")
        except Exception as e:
            self._add_error(f"无法加载状态：{e}")

    def _cmd_plan(self, _: str) -> None:
        self.session.mode = "plan"
        self._update_status()
        self._add_assistant("已切换到 [PLAN] 模式 - 只分析规划，不执行命令。")

    def _cmd_act(self, _: str) -> None:
        self.session.mode = "act"
        self._update_status()
        self._add_assistant("已切换到 [ACT] 模式 - 允许执行命令和写文件。")

    def _cmd_input(self, args: str) -> None:
        self.session.paper_path = args.strip().lstrip("@")
        self.session.input_resolved = False
        self._add_assistant(f"输入已设置：{self.session.paper_path}")

    def _cmd_repo(self, args: str) -> None:
        self.session.repo = args.strip() or None
        self._add_assistant(f"仓库：{self.session.repo or '-'}")

    def _cmd_repo_dir(self, args: str) -> None:
        self.session.repo_dir = args.strip().lstrip("@")
        self._add_assistant(f"本地仓库：{self.session.repo_dir}")

    def _cmd_backend(self, args: str) -> None:
        backend = args.strip()
        if backend not in {"none", "local", "venv", "docker"}:
            self._add_error("后端必须是：none、local、venv 或 docker")
            return
        self.session.backend = backend
        self._update_status()
        self._add_assistant(f"后端已设置为：{backend}")

    def _cmd_workspace(self, args: str) -> None:
        self.session.workspace = args.strip() or self.session.workspace
        self._add_assistant(f"工作目录：{self.session.workspace}")

    def _cmd_timeout(self, args: str) -> None:
        try:
            self.session.timeout_minutes = int(args.strip())
            self._add_assistant(f"超时：{self.session.timeout_minutes} 分钟")
        except ValueError:
            self._add_error("用法：/timeout 分钟数")

    def _cmd_repairs(self, args: str) -> None:
        try:
            self.session.max_repair_attempts = int(args.strip())
            self._add_assistant(f"最大修复次数：{self.session.max_repair_attempts}")
        except ValueError:
            self._add_error("用法：/repairs 次数")

    def _cmd_run(self, _: str) -> None:
        self._start_pipeline()

    def _cmd_report(self, _: str) -> None:
        path = self._report_path()
        if path is None:
            self._add_assistant("报告暂不可用。")
            return
        self._add_assistant(f"路径：{path}")
        self._add_assistant(path.read_text(encoding="utf-8")[:2500])

    def _cmd_logs(self, args: str) -> None:
        s = self.session
        if not s.task_dir:
            self._add_assistant("当前会话尚未运行过任务。")
            return
        kind = args.strip() or "smoke"
        candidates = {
            "env": Path(s.task_dir) / "env" / "venv_build.log",
            "build": Path(s.task_dir) / "env" / "build.log",
            "smoke": Path(s.task_dir) / "runs" / "smoke_001" / "run_summary.json",
            "stderr": Path(s.task_dir) / "runs" / "smoke_001" / "stderr.log",
            "stdout": Path(s.task_dir) / "runs" / "smoke_001" / "stdout.log",
        }
        path = candidates.get(kind)
        if path is None:
            self._add_assistant("用法：/logs env|build|smoke|stderr|stdout")
            return
        if not path.exists():
            self._add_assistant(f"未找到：{path}")
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        self._add_assistant(str(path))
        self._add_assistant(text[-3000:] if len(text) > 3000 else text)

    def _cmd_quit(self, _: str) -> None:
        self.exit()

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def _submit_paper(self, value: str) -> None:
        paper_input = value.strip().lstrip("@")
        if not paper_input:
            self._add_assistant("请输入本地论文 PDF 路径。")
            return
        self.session.paper_path = paper_input
        self.session.input_resolved = False
        self._add_user(paper_input)
        self._add_assistant("收到。我先确认这个本地 PDF 是否可读取。")
        self._start_pipeline()

    def _start_pipeline(self) -> None:
        s = self.session
        if not s.paper_path:
            self._add_assistant("先把本地论文 PDF 路径发给我，例如 @/path/to/paper.pdf。")
            return
        self.agent_running = True
        self._update_status()
        if self._composer:
            self._composer.set_disabled(True)

        # Run pipeline in a thread so TUI stays responsive
        asyncio.create_task(self._run_pipeline_async())

    async def _run_pipeline_async(self) -> None:
        s = self.session
        try:
            # Resolve input
            if not s.input_resolved:
                self.call_from_thread(self._add_assistant, "正在解析输入并确认本地 PDF 文件。")
                try:
                    resolution = await asyncio.get_event_loop().run_in_executor(
                        None, self.resolver.resolve, s.paper_path or ""
                    )
                except Exception as e:
                    s.status = "input_failed"
                    self.call_from_thread(self._add_error, f"输入解析失败：{e}")
                    return

                self.call_from_thread(self._append_resolution, resolution)
                if not resolution.success or not resolution.input_value:
                    s.status = "input_failed"
                    return
                s.paper_path = resolution.input_value
                s.input_resolved = True

            s.status = "running"
            self.call_from_thread(self._add_assistant, "开始复现流水线。")
            self.call_from_thread(self._update_status)

            # Run the blocking pipeline in executor
            def run_with_progress():
                def on_progress(event: ProgressEvent) -> None:
                    self.call_from_thread(
                        self._on_pipeline_progress, event
                    )
                with progress_events(on_progress):
                    return self.runner(
                        input_value=s.paper_path,
                        workspace=s.workspace,
                        backend=s.backend,
                        repo=s.repo,
                        repo_dir=s.repo_dir,
                        timeout_minutes=s.timeout_minutes,
                        max_repair_attempts=s.max_repair_attempts,
                    )

            state = await asyncio.get_event_loop().run_in_executor(None, run_with_progress)

            s.task_dir = state.task_dir
            s.status = state.report.final_status if state.report else state.status
            report_path = Path(state.task_dir) / "report" / "reproduction_smoke_report.md"
            s.report_path = str(report_path) if report_path.exists() else None

            self.call_from_thread(self._add_assistant, f"已完成：{s.status}")
            self.call_from_thread(self._update_status)

            if report_path.exists():
                self.call_from_thread(self._append_report, report_path)

        except Exception as e:
            s.status = "failed"
            self.call_from_thread(self._add_error, f"流水线异常退出：{e}")
        finally:
            self.agent_running = False
            self.call_from_thread(self._update_status)
            if self._composer:
                self.call_from_thread(self._composer.set_disabled, False)

    def _on_pipeline_progress(self, event: ProgressEvent) -> None:
        """Called from pipeline thread via call_from_thread."""
        stage = event.stage
        message = event.message
        detail = event.detail
        level = event.level

        # Try to update existing tool card or create new one
        if level == "info" and "started" in message:
            self._get_or_create_tool_card(stage, message)
        elif level == "info" and "completed" in message:
            pass  # duration will come separately
        elif level == "success":
            self._update_tool_card(stage, status="success", detail=detail)
        elif level == "error":
            self._update_tool_card(stage, status="failed", detail=detail)
        else:
            # Generic progress update
            card = self._get_or_create_tool_card(stage, message)
            card.update(detail=detail)

        # Also scroll timeline
        if self._timeline:
            self._timeline.scroll_end(animate=False)

    def _append_resolution(self, resolution: PaperInputResolution) -> None:
        if resolution.success:
            parts = ["本地 PDF 已确认" if resolution.exists else "输入格式已确认"]
            if resolution.title:
                parts.append(f"标题：{resolution.title}")
            self._add_assistant("；".join(parts))
            if resolution.reason:
                self._add_assistant(resolution.reason)
            return
        reason = resolution.failure_reason or resolution.reason or "无法把输入解析成可运行论文。"
        self._add_error(f"不能开始复现：{reason}")

    def _append_report(self, report_path: Path) -> None:
        s = self.session
        s.report_path = str(report_path)
        self._add_assistant(f"路径：{report_path}")
        text = report_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            self._add_assistant("报告文件为空")
            return
        preview = text[:4000]
        if len(text) > len(preview):
            preview += "\n\n...[已截断；使用 /report 查看完整报告]"
        self._add_assistant(preview)

    def _run_shell(self, command: str) -> None:
        import subprocess
        if not command:
            self._add_assistant("用法：!命令")
            return
        self._add_assistant(f"$ {command}")
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        except Exception as e:
            self._add_error(str(e))
            return
        output = (proc.stdout + proc.stderr).strip()
        self._add_assistant(output[-3000:] if output else f"exit {proc.returncode}")

    def _report_path(self) -> Path | None:
        s = self.session
        if s.report_path:
            path = Path(s.report_path)
            if path.exists():
                return path
        if s.task_dir:
            path = Path(s.task_dir) / "report" / "reproduction_smoke_report.md"
            if path.exists():
                return path
        return None

    # ------------------------------------------------------------------
    # Key binding actions
    # ------------------------------------------------------------------

    def action_clear_screen(self) -> None:
        if self._timeline:
            self._timeline.clear_messages()

    def action_toggle_plan_mode(self) -> None:
        if self.session.mode == "plan":
            self._cmd_act("")
        else:
            self._cmd_plan("")
