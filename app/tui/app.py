from __future__ import annotations

"""PaperAgentApp – Textual-based Claude Code-style TUI."""

import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static

from app.agents.input_resolver_agent import InputResolverAgent, PaperInputResolution
from app.core.file_utils import load_state
from app.core.progress import ProgressEvent, progress_events
from app.core.state import TaskState
from app.runtime.events import AgentEvent
from app.runtime.session import Session, SessionStore, make_progress_bridge

from .widgets import Composer, MessageTimeline, StatusBar, ToolCard, HeaderLogo
from .panels import SessionPanel, PipelinePanel, StageView, HelpPanel, ArtifactPanel
from .commands import COMMANDS, RUNNING_SAFE_COMMANDS
from . import theme as T

PipelineRunner = Callable[..., TaskState]

SLASH_COMMANDS_SET: set[str] = set(COMMANDS.keys())


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
    if command not in SLASH_COMMANDS_SET:
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
    #main-content {
        height: 1fr;
    }
    #timeline-area {
        height: 1fr;
        width: 1fr;
    }
    #right-panel {
        width: 34;
        height: 1fr;
    }
    SessionPanel {
        width: 28;
        height: 1fr;
    }
    PipelinePanel {
        width: 34;
        height: 1fr;
    }
    HelpPanel {
        width: 34;
        height: 1fr;
    }
    ArtifactPanel {
        width: 34;
        height: 1fr;
    }
    """

    TITLE = "Paper Reproduct Agent"
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=True),
        Binding("ctrl+l", "clear_screen", "清屏", show=True),
        Binding("ctrl+p", "toggle_plan_mode", "PLAN/ACT", show=True),
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
        self._pending_shell: str | None = None
        self._active_panel = "pipeline"

        # Widget refs
        self._header: HeaderLogo | None = None
        self._timeline: MessageTimeline | None = None
        self._status_bar: StatusBar | None = None
        self._composer: Composer | None = None
        self._session_panel: SessionPanel | None = None
        self._pipeline_panel: PipelinePanel | None = None
        self._help_panel: HelpPanel | None = None
        self._artifact_panel: ArtifactPanel | None = None

        # Tool cards tracking
        self._tool_cards: dict[str, ToolCard] = {}
        self._active_tool_by_stage: dict[str, str] = {}

    # ── Compose ──────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield HeaderLogo(
            session_id=self.session.id,
            backend=self.session.backend,
            mode="ACT",
            status="draft",
        )

        with Horizontal(id="main-content"):
            # Left: Session panel
            yield SessionPanel(classes="left-panel")

            # Center: Timeline
            yield MessageTimeline(id="timeline-area")

            # Right: dynamic panel (pipeline / help / artifacts)
            yield PipelinePanel(backend=self.session.backend, id="right-panel")

        yield StatusBar()
        yield Composer(mode="act")

    def on_mount(self) -> None:
        self._header = self.query_one(HeaderLogo)
        self._timeline = self.query_one(MessageTimeline)
        self._status_bar = self.query_one(StatusBar)
        self._composer = self.query_one(Composer)
        self._session_panel = self.query_one(SessionPanel)
        self._pipeline_panel = self.query_one(PipelinePanel)

        self._composer.focus_input()
        self._add_assistant(
            "欢迎使用 **Paper Reproduct Agent**。\n\n"
            "输入本地论文 PDF 路径开始，例如：\n\n"
            "    `@/path/to/paper.pdf`\n\n"
            "常用命令：\n"
            "  `/backend conda`\n"
            "  `/repo https://github.com/user/repo`\n"
            "  `/run`\n"
            "  `/logs smoke`\n"
            "  `/report`\n\n"
            "输入 `/help` 查看所有命令。"
        )
        self._update_status()
        self._sync_session_panel()

    # ── Message helpers ──────────────────────────────────────

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

    def _add_system(self, text: str) -> None:
        if self._timeline:
            self._timeline.add_system(text)

    def _add_report_msg(self, text: str) -> None:
        if self._timeline:
            self._timeline.add_report(text)

    def _update_status(self) -> None:
        if self._status_bar:
            paper_name = "-"
            if self.session.paper_path:
                paper_name = Path(self.session.paper_path).name
            self._status_bar.update_info(
                mode=self.session.mode.upper(),
                session=self.session.id,
                backend=self.session.backend,
                status=self.session.status,
                paper=paper_name,
                panel=self._active_panel,
            )
        if self._header:
            self._header.update_summary(
                session_id=self.session.id,
                backend=self.session.backend,
                mode=self.session.mode.upper(),
                status=self.session.status,
            )

    def _sync_session_panel(self) -> None:
        if self._session_panel:
            s = self.session
            self._session_panel.update_session(
                session_id=s.id,
                mode=s.mode,
                backend=s.backend,
                workspace=s.workspace,
                paper=s.paper_path or "",
                repo=s.repo or "",
                repo_dir=s.repo_dir or "",
                timeout=str(s.timeout_minutes),
                repairs=str(s.max_repair_attempts),
                task_dir=s.task_dir or "",
                report_path=s.report_path or "",
                status=s.status,
                cancel_requested=s.cancel_requested,
            )

    def _sync_artifact_panel(self) -> None:
        if not self._artifact_panel or not self.session.task_dir:
            return
        td = Path(self.session.task_dir)
        self._artifact_panel.update_artifacts(
            task_dir=str(td),
            report_md=str(td / "report" / "reproduction_smoke_report.md"),
            report_json=str(td / "report" / "reproduction_smoke_report.json"),
            state_json=str(td / "state.json"),
            env_log=str(td / "env" / "conda_build.log"),
            smoke_log=str(td / "runs" / "smoke_001" / "stdout.log"),
            benchmark_log=str(td / "runs" / "benchmark_001" / "stderr.log"),
            reproduction_log=str(td / "runs" / "reproduction_001" / "stderr.log"),
        )

    # ── Panel switching ──────────────────────────────────────

    def _switch_panel(self, name: str) -> None:
        self._active_panel = name
        right = self.query_one("#right-panel")
        right.remove_children()

        if name == "session":
            right.mount(SessionPanel(classes="left-panel"))
            self._session_panel = self.query_one("#right-panel SessionPanel")
            self._sync_session_panel()
        elif name == "pipeline":
            right.mount(PipelinePanel(backend=self.session.backend))
            self._pipeline_panel = self.query_one("#right-panel PipelinePanel")
        elif name == "help":
            right.mount(HelpPanel())
            self._help_panel = self.query_one("#right-panel HelpPanel")
        elif name == "artifacts":
            right.mount(ArtifactPanel())
            self._artifact_panel = self.query_one("#right-panel ArtifactPanel")
            self._sync_artifact_panel()
        elif name == "none":
            # Keep empty
            pass

        self._update_status()

    # ── Tool card helpers ────────────────────────────────────

    def _create_tool_card(self, stage: str, message: str) -> ToolCard:
        key = f"{stage}:{len(self._tool_cards)}"
        card = ToolCard(name=stage, status="running", message=message)
        if self._timeline:
            self._timeline.mount(card)
            self._timeline.scroll_end(animate=False)
        self._tool_cards[key] = card
        self._active_tool_by_stage[stage] = key
        return card

    def _get_active_tool_card(self, stage: str) -> ToolCard | None:
        key = self._active_tool_by_stage.get(stage)
        if key is None:
            return None
        return self._tool_cards.get(key)

    def _get_or_create_tool_card(self, stage: str, message: str) -> ToolCard:
        existing = self._get_active_tool_card(stage)
        if existing is not None:
            existing.update(status="running", message=message)
            return existing
        return self._create_tool_card(stage, message)

    def _update_tool_card(
        self,
        stage: str,
        status: str,
        detail: str | None = None,
        duration: float | None = None,
    ) -> None:
        """Update active tool card and release mapping on terminal states."""
        card = self._get_active_tool_card(stage)
        if card is not None:
            card.update(status=status, detail=detail, duration=duration)
        if status in ("success", "failed"):
            self._active_tool_by_stage.pop(stage, None)

    # ── Progress bridge ──────────────────────────────────────

    def _start_progress_bridge(self) -> None:
        _stage_times: dict[str, float] = {}

        def on_event(ev: ProgressEvent) -> None:
            name = ev.stage
            now = time.monotonic()

            # Track duration
            if ev.phase == "start":
                _stage_times[name] = now
            duration = None
            if name in _stage_times and ev.phase in ("finish", "fail"):
                duration = now - _stage_times[name]

            # Map phase → status
            phase_status = {
                "start": "running",
                "finish": "success",
                "fail": "failed",
                "progress": "running",
                "skip": "skipped",
            }
            status = phase_status.get(ev.phase, "running")

            # Update tool card
            card = self._get_or_create_tool_card(name, ev.message)
            card.update(
                status=status,
                message=ev.message,
                detail=ev.detail or "",
                duration=duration,
            )

            # Update pipeline panel
            if self._pipeline_panel:
                self._pipeline_panel.update_from_name(
                    name=name,
                    status=status,
                    message=ev.message,
                    detail=ev.detail or "",
                    duration=duration,
                )

            if ev.phase in ("finish", "fail"):
                self._sync_artifact_panel()

        self._bridge = on_event
        progress_events(on_event)

    # ── Composer input ───────────────────────────────────────

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        line = event.value
        if not line:
            return
        self.handle_line(line)

    def handle_line(self, line: str) -> None:
        if self._pending_shell is not None:
            self._confirm_shell(line)
            return

        command, args = parse_command(line)
        if command == "":
            return

        # Running guard
        if self.agent_running and command not in RUNNING_SAFE_COMMANDS:
            safe = " ".join(f"/{c}" for c in sorted(RUNNING_SAFE_COMMANDS - {"!"}))
            self._add_assistant(f"Agent 正在运行。可用命令：{safe}")
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
            "cancel": self._cmd_cancel,
            "sessions": self._cmd_sessions,
            "resume": self._cmd_resume,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "panel": self._cmd_panel,
            "artifact": self._cmd_artifact,
            "open-report": self._cmd_open_report,
            "mode": self._cmd_mode,
            "reset": self._cmd_reset,
        }
        handler = handlers.get(command)
        if handler is None:
            self._add_assistant(
                f"未知命令 /{command}。输入 /help 查看可用命令。\n"
                f"用法示例：/{command} <参数>"
            )
            return
        handler(args)

    # ── Commands ──────────────────────────────────────────────

    def _cmd_help(self, args: str) -> None:
        cat = args.strip().lower() if args else ""
        lines = ["**可用命令**", ""]
        shown = False
        for name, meta in COMMANDS.items():
            if name == "exit":
                continue
            if cat and meta.category.lower().replace(" ", "-") != cat:
                continue
            shown = True
            arg_str = f" {meta.args}" if meta.args else ""
            safe = " [safe]" if meta.safe_during_run else ""
            lines.append(f"- `/{name}{arg_str}` — {meta.description}{safe}")
        if not shown and cat:
            cats = sorted(set(m.category.lower().replace(" ", "-") for m in COMMANDS.values()))
            lines.append(f"类别 '{cat}' 未找到。可用类别：{', '.join(cats)}")
        self._add_assistant("\n".join(lines))

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
            self._add_assistant(
                f"**任务状态**\n\n"
                f"- Task: `{state.task_id}`\n"
                f"- Status: `{state.status}`\n"
                f"- Task dir: `{state.task_dir}`"
            )
            if state.report:
                self._add_assistant(f"- Final status: `{state.report.final_status}`")
        except Exception as e:
            self._add_error(f"无法加载状态：{e}")

    def _cmd_plan(self, _: str) -> None:
        self.session.mode = "plan"
        self._update_status()
        if self._composer:
            self._composer.set_mode("plan")
        self._add_assistant("已切换到 **[PLAN]** 模式 —— 只分析规划，不执行命令。")

    def _cmd_act(self, _: str) -> None:
        self.session.mode = "act"
        self._update_status()
        if self._composer:
            self._composer.set_mode("act")
        self._add_assistant("已切换到 **[ACT]** 模式 —— 允许执行。")

    def _cmd_mode(self, _: str) -> None:
        self._add_assistant(f"当前模式：**{self.session.mode.upper()}**")

    def _cmd_input(self, args: str) -> None:
        self.session.paper_path = args.strip().lstrip("@")
        self.session.input_resolved = False
        self._sync_session_panel()
        self._add_assistant(f"输入已设置：`{self.session.paper_path}`")

    def _cmd_repo(self, args: str) -> None:
        self.session.repo = args.strip() or None
        self._sync_session_panel()
        self._add_assistant(f"仓库：{self.session.repo or '-'}")

    def _cmd_repo_dir(self, args: str) -> None:
        self.session.repo_dir = args.strip().lstrip("@")
        self._sync_session_panel()
        self._add_assistant(f"本地仓库：{self.session.repo_dir}")

    def _cmd_backend(self, args: str) -> None:
        backend = args.strip().lower()
        if backend:
            if backend not in {"none", "local", "venv", "conda", "docker"}:
                self._add_error("后端必须是：none、local、venv、conda 或 docker\n用法：`/backend conda`")
                return
            self.session.backend = backend
            self._sync_session_panel()
            self._add_assistant(f"后端已设置为：**{backend}**")
            if self._pipeline_panel:
                self._pipeline_panel.reset(backend)
        else:
            opts = " | ".join(f"**{b}**" if b == self.session.backend else b for b in ["none", "local", "venv", "conda", "docker"])
            self._add_assistant(f"可用后端：{opts}\n当前：**{self.session.backend}**")

    def _cmd_workspace(self, args: str) -> None:
        self.session.workspace = args.strip() or self.session.workspace
        self._sync_session_panel()
        self._add_assistant(f"工作目录：`{self.session.workspace}`")

    def _cmd_timeout(self, args: str) -> None:
        try:
            self.session.timeout_minutes = int(args.strip())
            self._sync_session_panel()
            self._add_assistant(f"超时：{self.session.timeout_minutes} 分钟")
        except (ValueError, TypeError):
            self._add_error("用法：`/timeout <分钟数>`（整数）")

    def _cmd_repairs(self, args: str) -> None:
        try:
            self.session.max_repair_attempts = int(args.strip())
            self._sync_session_panel()
            self._add_assistant(f"最大修复次数：{self.session.max_repair_attempts}")
        except (ValueError, TypeError):
            self._add_error("用法：`/repairs <次数>`（整数）")

    def _cmd_panel(self, args: str) -> None:
        name = args.strip().lower() or "pipeline"
        valid = {"session", "pipeline", "help", "artifacts", "none"}
        if name not in valid:
            self._add_error(f"面板必须是：{', '.join(valid)}\n用法：`/panel help`")
            return
        self._switch_panel(name)
        self._add_system(f"已切换到 **{name}** 面板")

    def _cmd_artifact(self, _: str) -> None:
        self._switch_panel("artifacts")
        self._sync_artifact_panel()
        if not self.session.task_dir:
            self._add_assistant("尚未运行任务，没有产物。输入 `/run` 开始。")
        else:
            self._add_assistant(f"当前 task dir: `{self.session.task_dir}`")

    def _cmd_open_report(self, _: str) -> None:
        if not self.session.report_path:
            self._add_assistant("尚未生成报告。输入 `/run` 开始。")
            return
        rp = self.session.report_path
        self._add_report_msg(f"报告路径：`{rp}`")

    def _cmd_reset(self, _: str) -> None:
        self.session.paper_path = None
        self.session.repo = None
        self.session.repo_dir = None
        self.session.input_resolved = False
        self.session.status = "draft"
        self.session.task_dir = None
        self.session.report_path = None
        self.session.cancel_requested = False
        self._sync_session_panel()
        self._tool_cards.clear()
        self._active_tool_by_stage.clear()
        if self._pipeline_panel:
            self._pipeline_panel.reset(self.session.backend)
        self._add_assistant("会话已重置（磁盘文件未删除）。")

    @staticmethod
    def _status_label(status: str) -> str:
        return {"success": "✓", "failed": "✗", "running": "●", "cancelled": "○"}.get(status, "–")

    def _cmd_run(self, _: str) -> None:
        paper = self.session.paper_path
        if not paper:
            self._add_error("请先使用 /input <pdf路径> 设置论文文件。")
            return

        if not Path(paper).is_file():
            self._add_error(f"文件不存在：`{paper}`")
            return

        self._add_user(f"复现论文：{paper}")
        self._add_assistant("收到，正在确认本地 PDF 是否可读取。")

        if self.session.mode == "plan":
            self._add_assistant(
                "当前为 **PLAN** 模式，只显示执行计划。\n"
                "Pipeline 将会运行以下阶段：\n"
                "1. 解析论文 PDF\n"
                "2. LLM 分析任务\n"
                "3. GitHub 搜索\n"
                "4. 仓库评估\n"
                "5. 构建环境\n"
                "6. Smoke 测试\n"
                "7. Benchmark 复现\n"
                "8. 轻量复现\n"
                "9. 写报告\n\n"
                "输入 `/act` 切换模式后重试 `/run`。"
            )
            return

        # Run pipeline
        self.agent_running = True
        self.session.status = "running"
        self.session.cancel_requested = False
        self._update_status()
        self._sync_session_panel()
        if self._composer:
            self._composer.set_running(True)
        if self._pipeline_panel:
            self._pipeline_panel.reset(self.session.backend)

        self._start_progress_bridge()

        def _cancel_check() -> bool:
            return self.session.cancel_requested

        self.run_worker(
            self._do_run(paper, _cancel_check),
            exclusive=False,
        )

    async def _do_run(self, paper: str, cancel_check) -> None:
        try:
            state = await asyncio.to_thread(
                self.runner,
                paper,
                self.session.workspace,
                self.session.backend,
                self.session.repo,
                self.session.repo_dir,
                self.session.timeout_minutes,
                self.session.max_repair_attempts,
                cancel_check,
            )

            self.session.task_dir = state.task_dir
            self.session.status = getattr(state, "status", "completed")
            report_path = Path(state.task_dir) / "report" / "reproduction_smoke_report.md"
            if report_path.exists():
                self.session.report_path = str(report_path)

            # Build final message
            final = getattr(state.report, "final_status", "unknown") if state.report else "unknown"
            self._add_assistant(
                f"**Pipeline 完成**\n\n"
                f"- Final status: `{final}`\n"
                f"- Report: `{report_path}`"
            )

            if report_path.exists():
                preview = report_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                self._add_report_msg(preview)

            self._sync_session_panel()
            self._sync_artifact_panel()

        except Exception as e:
            self.session.status = "failed"
            self._add_error(f"Pipeline 异常：{e}")
        finally:
            self.agent_running = False
            if self._composer:
                self._composer.set_running(False)
                self._composer.focus_input()
            self._update_status()
            self._sync_session_panel()
            self._sync_artifact_panel()

    def _cmd_cancel(self, _: str) -> None:
        if not self.agent_running:
            self._add_assistant("当前没有运行中的任务。")
            return
        self.session.cancel_requested = True
        self._add_system("已请求取消。等待当前步骤完成...")

    # ── Paper submission ─────────────────────────────────────

    def _submit_paper(self, text: str) -> None:
        self.session.paper_path = text.strip().lstrip("@")
        self.session.input_resolved = True
        self._add_user(text)
        self._sync_session_panel()

        # Resolve input
        try:
            resolution = self.resolver.resolve(text)
        except Exception as e:
            self._add_error(f"无法解析输入：{e}")
            return

        if not resolution.success:
            self._add_error(resolution.failure_reason or "输入无效")
            return

        self.session.paper_path = resolution.input_value or self.session.paper_path
        self._sync_session_panel()

        info_lines = [f"已解析论文路径：`{resolution.input_value}`"]
        if resolution.title:
            info_lines.append(f"标题：{resolution.title}")
        self._add_assistant("\n".join(info_lines))

        # Auto-run in ACT mode
        if self.session.mode == "act":
            self._cmd_run("")

    # ── Shell ─────────────────────────────────────────────────

    def _run_shell(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd:
            self._add_error("!shell 需要命令参数。例如：`!ls -la`")
            return
        self._pending_shell = cmd
        self._add_assistant(f"即将执行 shell 命令：\n```\n{cmd}\n```\n输入 `yes` 确认，或输入其他内容取消。")

    def _confirm_shell(self, line: str) -> None:
        if line.strip().lower() not in ("yes", "y"):
            self._add_assistant("已取消。")
            self._pending_shell = None
            return
        cmd = self._pending_shell
        self._pending_shell = None
        import subprocess
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout[:3000] or "(no stdout)"
            if result.stderr:
                output += f"\n\nstderr:\n{result.stderr[:1000]}"
            self._add_tool_message(f"$ {cmd}\n\n{output}", "Shell")
        except subprocess.TimeoutExpired:
            self._add_error("命令超时（30秒）。")
        except Exception as e:
            self._add_error(f"命令执行失败：{e}")

    def _add_tool_message(self, text: str, label: str = "工具") -> None:
        if self._timeline:
            self._timeline.add_tool(text, label=label)

    # ── Logs ──────────────────────────────────────────────────

    def _cmd_logs(self, args: str) -> None:
        log_type = args.strip().lower()
        if not self.session.task_dir:
            self._add_assistant("尚未运行任务。先 `/run` 开始。")
            return

        td = Path(self.session.task_dir)
        log_map: dict[str, Path] = {
            "env": td / "env" / "conda_build.log",
            "conda": td / "env" / "conda_build.log",
            "venv": td / "env" / "venv_build.log",
            "build": td / "env" / "conda_build.log",
            "smoke": td / "runs" / "smoke_001" / "stdout.log",
            "benchmark": td / "runs" / "benchmark_001" / "stderr.log",
            "reproduction": td / "runs" / "reproduction_001" / "stderr.log",
            "stderr": td / "runs" / "smoke_001" / "stderr.log",
            "stdout": td / "runs" / "smoke_001" / "stdout.log",
        }

        if log_type not in log_map:
            opts = ", ".join(sorted(log_map.keys()))
            self._add_assistant(
                f"未知日志类型 `{log_type}`。可用：{opts}\n"
                f"用法：`/logs smoke`"
            )
            return

        path = log_map[log_type]
        if not path.exists():
            self._add_assistant(f"日志文件不存在：`{path}`")
            return

        content = path.read_text(encoding="utf-8", errors="ignore")
        if len(content) > 5000:
            content = content[-5000:] + "\n\n... [dim](最后 5000 字符)[/]"
        self._add_tool_message(f"**{log_type} log** (`{path}`)\n\n```\n{content}\n```", "日志")

    # ── Report ───────────────────────────────────────────────

    def _cmd_report(self, _: str) -> None:
        if not self.session.task_dir:
            self._add_assistant("尚未运行任务。先 `/run` 开始。")
            return
        rp = Path(self.session.task_dir) / "report" / "reproduction_smoke_report.md"
        if not rp.exists():
            self._add_assistant(f"报告尚未生成。预期路径：`{rp}`")
            return
        content = rp.read_text(encoding="utf-8", errors="ignore")
        self._add_report_msg(f"报告：`{rp}`\n\n{content[:3000]}")

    # ── Sessions ─────────────────────────────────────────────

    def _cmd_sessions(self, _: str) -> None:
        sessions = self.store.list_sessions()
        if not sessions:
            self._add_assistant("没有已保存的会话。")
            return

        lines = [
            "| Session ID | Paper | Backend | Status | Created |",
            "|---|---|---|---|---|",
        ]
        for s in sessions[:20]:
            sid = s.get("id", "")[:8]
            paper = Path(s.get("paper_path", "")).name if s.get("paper_path") else "-"
            be = s.get("backend", "-")
            st = s.get("status", "-")
            created = s.get("created_at", "")
            if isinstance(created, (int, float)):
                from datetime import datetime
                created = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
            lines.append(f"| {sid} | {paper} | {be} | {st} | {created} |")
        self._add_assistant("\n".join(lines))

    def _cmd_resume(self, args: str) -> None:
        sid = args.strip()
        if not sid:
            self._add_error("用法：`/resume <session-id>`")
            return
        try:
            other_store = SessionStore(sid)
            data = other_store.load_snapshot()
            if data is None:
                self._add_error(f"会话 `{sid}` 未找到。")
                return
            self.session = Session(
                id=data.get("id", sid),
                paper_path=data.get("paper_path"),
                repo=data.get("repo"),
                repo_dir=data.get("repo_dir"),
                backend=data.get("backend", "conda"),
                workspace=data.get("workspace", "./workspace"),
                timeout_minutes=data.get("timeout_minutes", 30),
                max_repair_attempts=data.get("max_repair_attempts", 5),
                status=data.get("status", "draft"),
                mode=data.get("mode", "act"),
                task_dir=data.get("task_dir"),
                report_path=data.get("report_path"),
            )
            self.store = other_store
            self._sync_session_panel()
            self._update_status()
            self._add_assistant(f"已恢复会话 `{sid}`（状态：{self.session.status}）")
        except Exception as e:
            self._add_error(f"恢复失败：{e}")

    def _cmd_quit(self, _: str) -> None:
        self.exit()

    # ── Bindings ──────────────────────────────────────────────

    def action_toggle_plan_mode(self) -> None:
        if self.session.mode == "plan":
            self._cmd_act("")
        else:
            self._cmd_plan("")

    def action_clear_screen(self) -> None:
        self._cmd_clear("")
