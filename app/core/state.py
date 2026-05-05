from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


BackendType = Literal["none", "local", "venv", "docker"]
InputType = Literal["arxiv", "pdf", "unknown"]
TaskStatus = Literal[
    "created",
    "paper_ingested",
    "paper_understood",
    "repo_found",
    "repo_evaluated",
    "env_built",
    "smoke_ran",
    "report_written",
    "cancelled",
    "failed",
]

FinalStatus = Literal[
    "success",
    "partial_success_help_only",
    "repo_found_but_env_failed",
    "repo_found_but_smoke_failed",
    "repo_found_smoke_not_run",
    "repo_not_found",
    "paper_parse_failed",
    "skipped_docker",
    "failed",
]


class PaperInput(BaseModel):
    raw_input: str
    input_type: InputType = "unknown"
    local_pdf_path: Optional[str] = None
    arxiv_id: Optional[str] = None


class PaperMetadata(BaseModel):
    title: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    arxiv_id: Optional[str] = None
    pdf_path: Optional[str] = None
    parsed_text_path: Optional[str] = None
    parse_confidence: float = 0.0


class ReproductionBrief(BaseModel):
    task: Optional[str] = None
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    method_keywords: list[str] = Field(default_factory=list)
    github_links_in_paper: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RepoCandidate(BaseModel):
    url: str
    owner: Optional[str] = None
    name: Optional[str] = None
    stars: Optional[int] = None
    source: Literal["paper", "github_search", "manual", "local"] = "github_search"
    score: float = 0.0
    confidence: Literal["high", "medium", "low"] = "low"
    reasons: list[str] = Field(default_factory=list)
    local_path: Optional[str] = None


class RepoEvaluation(BaseModel):
    repo_dir: Optional[str] = None

    has_readme: bool = False
    has_requirements: bool = False
    has_environment_yml: bool = False
    has_dockerfile: bool = False
    has_setup_py_or_pyproject: bool = False

    candidate_scripts: list[str] = Field(default_factory=list)
    candidate_configs: list[str] = Field(default_factory=list)

    runnable_score: float = 0.0
    risk_flags: list[str] = Field(default_factory=list)


class EnvironmentBuildResult(BaseModel):
    dockerfile_path: Optional[str] = None
    image_tag: Optional[str] = None
    environment_path: Optional[str] = None
    python_executable: Optional[str] = None
    python_paths: list[str] = Field(default_factory=list)
    build_success: bool = False
    skipped: bool = False
    failure_type: Optional[str] = None
    failure_summary: Optional[str] = None
    build_log_path: Optional[str] = None
    install_actions: list[dict[str, Any]] = Field(default_factory=list)


class SmokeCommand(BaseModel):
    argv: list[str]
    display: str
    kind: Literal["help", "demo", "pytest"] = "help"


class SmokeRunResult(BaseModel):
    command: Optional[SmokeCommand] = None
    success: bool = False
    exit_code: Optional[int] = None
    timed_out: bool = False
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    summary: Optional[str] = None
    failure_type: Optional[str] = None
    failure_evidence: Optional[str] = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    repair_actions: list[dict[str, Any]] = Field(default_factory=list)


class ReportResult(BaseModel):
    final_status: FinalStatus
    report_markdown_path: str
    report_json_path: Optional[str] = None
    short_conclusion: str


class StepTiming(BaseModel):
    step: str
    started_at: str
    ended_at: str
    duration_ms: int
    success: bool


class ApiCallRecord(BaseModel):
    provider: str
    purpose: str
    success: bool
    duration_ms: Optional[int] = None


class TaskState(BaseModel):
    task_id: str
    input_value: str
    workspace_dir: str
    task_dir: str
    created_at: datetime = Field(default_factory=datetime.now)
    backend: BackendType = "docker"

    paper_input: Optional[PaperInput] = None
    paper_metadata: Optional[PaperMetadata] = None
    reproduction_brief: Optional[ReproductionBrief] = None

    repo_candidates: list[RepoCandidate] = Field(default_factory=list)
    selected_repo: Optional[RepoCandidate] = None
    repo_evaluation: Optional[RepoEvaluation] = None

    env_build: Optional[EnvironmentBuildResult] = None
    smoke_run: Optional[SmokeRunResult] = None
    report: Optional[ReportResult] = None

    step_timings: list[StepTiming] = Field(default_factory=list)
    api_calls: list[ApiCallRecord] = Field(default_factory=list)

    status: TaskStatus = "created"
    errors: list[dict[str, Any]] = Field(default_factory=list)
