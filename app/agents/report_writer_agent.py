from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

import jinja2

from app.core.file_utils import save_json
from app.core.state import TaskState, ReportResult
from app.tools.llm import call_llm_json

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_SYSTEM_PROMPT = """\
你是一个论文复现助手。根据下面的 smoke 测试结果，生成简洁的结论和可操作的建议。

请用中文回复，返回 JSON 对象：
- "conclusion": 1-3 句自然语言总结，说明整体结果，具体指出哪些步骤成功、哪些失败。
- "next_steps": 3-5 条具体的建议，告诉用户下一步应该做什么。尽量引用具体的文件路径或命令。

要求简洁实用，不要猜测。"""


_SMOKE_ENV_FAILURE_TYPES = {
    "missing_dependency",
    "cuda_error",
    "runtime_linker_error",
}


class ReportWriterAgent:
    def run(self, state: TaskState) -> TaskState:
        task_dir = Path(state.task_dir)
        report_dir = task_dir / "report"
        report_dir.mkdir(parents=True, exist_ok=True)

        final_status = self._determine_final_status(state)

        # Try LLM for conclusion and next steps
        llm_result = self._llm_generate_insights(state, final_status)
        if llm_result:
            short_conclusion = llm_result.get("conclusion", self._short_conclusion(final_status))
            next_steps = llm_result.get("next_steps", self._next_steps(final_status))
        else:
            logger.info("LLM unavailable or failed, falling back to template conclusion")
            short_conclusion = self._short_conclusion(final_status)
            next_steps = self._next_steps(final_status)

        template = jinja2.Template(
            (_TEMPLATES_DIR / "smoke_report.md.j2").read_text(encoding="utf-8")
        )

        report_content = template.render(
            timestamp=datetime.now().isoformat(),
            task_id=state.task_id,
            final_status=final_status,
            backend=state.backend,
            short_conclusion=short_conclusion,
            next_steps=next_steps,
            input=state.paper_input,
            paper=state.paper_metadata,
            brief=state.reproduction_brief,
            selected_repo=state.selected_repo,
            repo_candidates=state.repo_candidates[:5],
            repo_eval=state.repo_evaluation,
            env_build=state.env_build,
            smoke_run=state.smoke_run,
            errors=state.errors,
            step_timings=state.step_timings,
            api_calls=state.api_calls,
        )

        md_path = report_dir / "reproduction_smoke_report.md"
        json_path = report_dir / "reproduction_smoke_report.json"

        md_path.write_text(report_content, encoding="utf-8")

        report = ReportResult(
            final_status=final_status,
            report_markdown_path=str(md_path),
            report_json_path=str(json_path),
            short_conclusion=short_conclusion,
        )

        state.report = report
        save_json(json_path, report)

        state.status = "report_written"
        return state

    def _llm_generate_insights(self, state: TaskState, final_status: str) -> dict | None:
        lines = [f"Final status: {final_status}"]

        if state.paper_metadata and state.paper_metadata.title:
            lines.append(f"Paper: {state.paper_metadata.title}")

        if state.selected_repo:
            lines.append(f"Repo: {state.selected_repo.url}")

        if state.repo_evaluation:
            lines.append(f"Runnable score: {state.repo_evaluation.runnable_score}")
            if state.repo_evaluation.risk_flags:
                lines.append(f"Risk flags: {', '.join(state.repo_evaluation.risk_flags)}")

        if state.env_build:
            lines.append(f"Docker build success: {state.env_build.build_success}")
            if state.env_build.failure_summary:
                lines.append(f"Docker failure: {state.env_build.failure_summary}")

        if state.smoke_run:
            if state.smoke_run.command:
                lines.append(f"Smoke command: {state.smoke_run.command.display}")
            lines.append(f"Smoke success: {state.smoke_run.success}")
            if state.smoke_run.exit_code is not None:
                lines.append(f"Exit code: {state.smoke_run.exit_code}")
            if state.smoke_run.summary:
                lines.append(f"Smoke summary: {state.smoke_run.summary}")
            if state.smoke_run.failure_type:
                lines.append(f"Smoke failure type: {state.smoke_run.failure_type}")
            if state.smoke_run.failure_evidence:
                lines.append(f"Smoke failure evidence: {state.smoke_run.failure_evidence}")

        if state.errors:
            lines.append("Errors:")
            for err in state.errors:
                lines.append(f"  - {err}")

        return call_llm_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt="\n".join(lines),
            purpose="report_generation",
        )

    def _determine_final_status(self, state: TaskState):
        if not state.paper_metadata:
            return "paper_parse_failed"

        if not state.selected_repo:
            return "repo_not_found"

        # backend=none: only static analysis, no execution
        if state.backend == "none" and state.repo_evaluation:
            return "repo_found_smoke_not_run"

        if state.env_build and not state.env_build.build_success and not state.env_build.skipped:
            return "repo_found_but_env_failed"

        # Check smoke_run results first (applies to both local and docker backends)
        if state.smoke_run and state.smoke_run.success:
            if state.smoke_run.command and state.smoke_run.command.kind == "help":
                return "partial_success_help_only"
            return "success"

        if state.smoke_run and not state.smoke_run.success:
            if state.smoke_run.failure_type in _SMOKE_ENV_FAILURE_TYPES:
                return "repo_found_but_env_failed"
            return "repo_found_but_smoke_failed"

        if state.env_build and state.env_build.skipped:
            return "skipped_docker"

        return "failed"

    def _short_conclusion(self, status: str) -> str:
        mapping = {
            "success": "仓库已找到，Smoke 测试命令执行成功。",
            "partial_success_help_only": "--help 命令运行正常。这是一个部分成功的 Smoke 测试，并非完整复现。",
            "repo_found_but_env_failed": "已找到代码仓库，但依赖或执行环境未准备好。",
            "repo_found_but_smoke_failed": "仓库已找到，但 Smoke 测试命令执行失败。",
            "repo_found_smoke_not_run": "已找到代码仓库并完成静态评估，未执行代码（backend=none）。",
            "repo_not_found": "未找到或未提供合适的代码仓库。",
            "paper_parse_failed": "论文解析失败。",
            "skipped_docker": "用户跳过了 Docker 构建和 Smoke 测试。",
            "failed": "流水线在得到结论性结果之前失败。",
        }
        return mapping.get(status, "未知状态。")

    def _next_steps(self, status: str) -> list[str]:
        if status == "success":
            return [
                "手动运行仓库文档中描述的评估命令。",
                "根据需要下载所需的数据集或模型权重。",
                "将输出结果与论文报告的指标进行对比。",
            ]

        if status == "partial_success_help_only":
            return [
                "查看仓库 README 了解实际的 demo 或评估命令。",
                "如果仓库提供了示例输入，尝试运行。",
                "在确认数据集和权重需求后再进行更大规模的实验。",
            ]

        if status == "repo_found_but_env_failed":
            return [
                "打开 env/build.log、env/venv_build.log 或 runs/smoke_001/stderr.log 查看第一个依赖错误。",
                "检查仓库是否需要特定版本的 Python、CUDA 或 PyTorch。",
                "优先使用 --backend docker 或 --backend venv 在隔离环境中重试。",
            ]

        if status == "repo_found_but_smoke_failed":
            return [
                "打开 runs/smoke_001/stderr.log 查看错误详情。",
                "检查命令是否需要数据集路径、权重文件或配置文件。",
                "尝试手动以 --help 模式运行命令。",
            ]

        if status == "repo_not_found":
            return [
                "使用 --repo 或 --repo-dir 手动指定仓库。",
                "在论文 PDF、项目主页、Papers with Code 或作者主页搜索代码仓库。",
                "找到仓库后重新运行。",
            ]

        if status == "paper_parse_failed":
            return [
                "确认输入是有效且可读取的本地 PDF 文件。",
                "如果原论文来自 arXiv，请先下载 PDF 后传入本地路径。",
                "检查 PDF 是否为扫描版或纯图片。",
            ]

        if status == "skipped_docker":
            return [
                "查看仓库的可运行分数评估。",
                "使用 --backend docker 重新运行以测试环境构建。",
                "使用 --repo-dir 进行更快的本地迭代。",
            ]

        if status == "repo_found_smoke_not_run":
            return [
                "使用 --backend local 在本地运行 smoke 命令。",
                "使用 --backend docker 构建完整 Docker 环境并测试。",
                "查看仓库可运行分数和候选脚本评估是否合理。",
            ]

        return [
            "检查 state.json 中失败的步骤。",
            "查看报告中记录的错误信息。",
            "使用 --repo-dir 重新运行以排除 GitHub 搜索和克隆问题。",
        ]
