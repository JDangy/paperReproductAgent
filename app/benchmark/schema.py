from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


BenchmarkLevel = Literal["L0", "L1", "L2", "L3"]
TaskFamily = Literal[
    "local_feature_matching",
    "zero_shot_classification",
    "asr",
    "sequence_labeling",
    "unknown",
]


class ExecutionBudget(BaseModel):
    target_level: BenchmarkLevel = "L3"
    max_runtime_minutes: int = 30
    max_dataset_size_gb: float = 1.0
    allow_large_downloads: bool = False
    allow_manual_registration: bool = False
    prefer_gpu: bool = True


class DatasetSpec(BaseModel):
    name: str
    split: Optional[str] = None
    source: Literal["paper", "official_repo", "bundled", "readme", "synthetic", "unknown"] = "unknown"
    size_estimate: Optional[str] = None
    size_gb: Optional[float] = None
    public: Optional[bool] = None
    requires_manual_registration: bool = False
    notes: list[str] = Field(default_factory=list)


class ModelSpec(BaseModel):
    name: Optional[str] = None
    checkpoint_source: Literal["paper", "official", "repo_default", "readme", "unknown"] = "unknown"
    precision: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class MetricSpec(BaseModel):
    name: str
    canonical_name: Optional[str] = None
    direction: Literal["higher_is_better", "lower_is_better", "informational"] = "informational"
    unit: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)


class BenchmarkSpec(BaseModel):
    id: str
    task_family: TaskFamily
    level: BenchmarkLevel
    title: str
    dataset: DatasetSpec
    model: ModelSpec = Field(default_factory=ModelSpec)
    command: list[str] = Field(default_factory=list)
    command_kind: Literal["official_script", "generated_runner", "readme_example", "manual_protocol"] = "official_script"
    expected_metrics: list[MetricSpec] = Field(default_factory=list)
    parser: dict[str, Any] = Field(default_factory=dict)
    reference: dict[str, Any] = Field(default_factory=dict)
    feasibility: dict[str, Any] = Field(default_factory=dict)
    generated_script_name: Optional[str] = None
    generated_script_body: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None

    @property
    def runnable(self) -> bool:
        return bool(self.command) and bool(self.feasibility.get("runnable", True))


class BenchmarkRunResult(BaseModel):
    selected_spec: Optional[BenchmarkSpec] = None
    candidate_specs: list[BenchmarkSpec] = Field(default_factory=list)
    eligible: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    success: bool = False
    exit_code: Optional[int] = None
    timed_out: bool = False
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    summary: Optional[str] = None
    failure_type: Optional[str] = None
    failure_evidence: Optional[str] = None
    target_level: BenchmarkLevel = "L3"
    achieved_level: Optional[BenchmarkLevel] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    reference_results: dict[str, Any] = Field(default_factory=dict)
    comparisons: list[dict[str, Any]] = Field(default_factory=list)
    protocol_match: dict[str, Any] = Field(default_factory=dict)
    downgrade_reasons: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    failure_diagnosis: dict[str, Any] = Field(default_factory=dict)
    parser_hints: dict[str, Any] = Field(default_factory=dict)
