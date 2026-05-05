from pathlib import Path
from datetime import datetime


class TaskPaths:
    def __init__(self, workspace_dir: str, task_id: str):
        self.workspace_dir = Path(workspace_dir)
        self.task_id = task_id
        self.task_dir = self.workspace_dir / "tasks" / task_id

        self.input_dir = self.task_dir / "input"
        self.paper_dir = self.task_dir / "paper"
        self.repos_dir = self.task_dir / "repos"
        self.evaluation_dir = self.task_dir / "evaluation"
        self.env_dir = self.task_dir / "env"
        self.runs_dir = self.task_dir / "runs"
        self.report_dir = self.task_dir / "report"

    @property
    def state_json_path(self) -> Path:
        return self.task_dir / "state.json"

    def create_all_dirs(self) -> None:
        self.task_dir.mkdir(parents=True, exist_ok=False)
        for path in [
            self.input_dir,
            self.paper_dir,
            self.repos_dir,
            self.evaluation_dir,
            self.env_dir,
            self.runs_dir,
            self.report_dir,
        ]:
            path.mkdir()


def generate_task_id() -> str:
    return datetime.now().strftime("task_%Y%m%d_%H%M%S_%f")
