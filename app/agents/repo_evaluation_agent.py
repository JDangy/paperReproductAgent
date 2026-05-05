from __future__ import annotations

from pathlib import Path

from app.core.file_utils import save_json
from app.core.state import TaskState, RepoEvaluation
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
            return state

        task_dir = Path(state.task_dir)
        repo_dir = task_dir / "repos" / "cloned_repo"

        try:
            if state.selected_repo.source == "local":
                copy_local_repo(Path(state.selected_repo.local_path), repo_dir)
            else:
                clone_repo(state.selected_repo.url, repo_dir)

            scan = scan_repo_structure(repo_dir)
            risk_flags = detect_risk_flags(repo_dir, scan)

            evaluation = RepoEvaluation(
                repo_dir=str(repo_dir),
                **scan,
                runnable_score=compute_runnable_score(scan),
                risk_flags=risk_flags,
            )

            state.repo_evaluation = evaluation
            save_json(task_dir / "evaluation" / "repo_score.json", evaluation)
            state.status = "repo_evaluated"

        except Exception as e:
            state.errors.append({"agent": "RepoEvaluationAgent", "error": str(e)})
            state.status = "failed"

        return state
