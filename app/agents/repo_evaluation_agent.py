from __future__ import annotations

from pathlib import Path

from app.core.file_utils import save_json
from app.core.progress import emit_progress
from app.core.state import TaskState, RepoEvaluation
from app.tools.llm import call_llm_json
from app.tools.repo_tool import (
    clone_repo,
    copy_local_repo,
    scan_repo_structure,
    compute_runnable_score,
    detect_risk_flags,
)


class RepoEvaluationAgent:
    def run(self, state: TaskState) -> TaskState:
        if not state.selected_repo:
            state.errors.append({"agent": "RepoEvaluationAgent", "error": "No selected repo"})
            state.status = "failed"
            emit_progress("Evaluate repo", "no selected repository", level="error")
            return state

        task_dir = Path(state.task_dir)
        repo_dir = task_dir / "repos" / "cloned_repo"

        try:
            if state.selected_repo.source == "local":
                emit_progress("Evaluate repo", "copying local repository", detail=state.selected_repo.local_path)
                copy_local_repo(Path(state.selected_repo.local_path), repo_dir)
            else:
                emit_progress("Evaluate repo", "cloning repository", detail=state.selected_repo.url)
                clone_repo(state.selected_repo.url, repo_dir)

            emit_progress("Evaluate repo", "scanning repository structure", detail=str(repo_dir))
            scan = scan_repo_structure(repo_dir)
            emit_progress(
                "Evaluate repo",
                "repository structure scanned",
                detail=f"{len(scan.get('candidate_scripts', []))} script(s), {len(scan.get('candidate_configs', []))} config(s)",
                candidate_script_count=len(scan.get("candidate_scripts", [])),
                candidate_config_count=len(scan.get("candidate_configs", [])),
            )
            emit_progress("Evaluate repo", "detecting risk flags")
            risk_flags = detect_risk_flags(repo_dir, scan)
            if risk_flags:
                emit_progress("Evaluate repo", "risk flags detected", level="warning", detail=", ".join(risk_flags[:5]), risk_flags=risk_flags)
            else:
                emit_progress("Evaluate repo", "no risk flags detected")
            emit_progress("Evaluate repo", "analyzing benchmark surface", detail="README and candidate scripts")
            benchmark_surface = _llm_analyze_benchmark_surface(repo_dir, scan, risk_flags)

            evaluation = RepoEvaluation(
                repo_dir=str(repo_dir),
                **scan,
                runnable_score=compute_runnable_score(scan),
                risk_flags=risk_flags,
                benchmark_surface=benchmark_surface or {},
            )

            state.repo_evaluation = evaluation
            save_json(task_dir / "evaluation" / "repo_score.json", evaluation)
            state.status = "repo_evaluated"
            emit_progress(
                "Evaluate repo",
                "repo evaluation saved",
                detail=f"runnable_score={evaluation.runnable_score:.2f}",
                runnable_score=evaluation.runnable_score,
                repo_dir=str(repo_dir),
            )

        except Exception as e:
            state.errors.append({"agent": "RepoEvaluationAgent", "error": str(e)})
            state.status = "failed"
            emit_progress("Evaluate repo", "repo evaluation error", level="error", detail=str(e))

        return state


_SURFACE_PROMPT = """\
You are a repository benchmark surface analysis assistant.

Given a research repository scan, README excerpt, and script excerpts, identify
official benchmark/evaluation surfaces without creating paper-specific recipes.

Return a JSON object with exactly these keys:
- "official_eval_commands": list of command strings likely to run official eval/benchmark
- "demo_commands": list of command strings likely to run demos/examples
- "dataset_requirements": list of required datasets or paths
- "weight_requirements": list of required weights/checkpoints
- "likely_metrics": list of metric names likely produced by eval scripts
- "benchmark_files": list of files that appear to define benchmark protocol
- "confidence": float between 0 and 1
"""


def _llm_analyze_benchmark_surface(repo_dir: Path, scan: dict, risk_flags: list[str]) -> dict | None:
    readme = _read_readme(repo_dir)
    script_excerpts = []
    for script in scan.get("candidate_scripts", [])[:12]:
        path = repo_dir / script
        if not path.exists() or not path.is_file():
            continue
        script_excerpts.append({
            "path": script,
            "excerpt": path.read_text(encoding="utf-8", errors="ignore")[:1600],
        })

    payload = {
        "scan": scan,
        "risk_flags": risk_flags,
        "readme_excerpt": readme[:6000],
        "script_excerpts": script_excerpts,
    }
    return call_llm_json(
        system_prompt=_SURFACE_PROMPT,
        user_prompt=json_dumps(payload),
        purpose="repo_benchmark_surface_analysis",
        max_tokens=3072,
    )


def _read_readme(repo_dir: Path) -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = repo_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
