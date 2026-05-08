from __future__ import annotations

from pathlib import Path

from app.benchmark.adapters import (
    ASRAdapter,
    AdapterContext,
    LocalFeatureMatchingAdapter,
    SequenceLabelingAdapter,
    ZeroShotClassificationAdapter,
)
from app.benchmark.ontology import classify_task_family
from app.benchmark.schema import BenchmarkSpec, ExecutionBudget
from app.benchmark.script_miner import mine_script_signals
from app.core.naming import stable_paper_slug
from app.core.state import TaskState


ADAPTERS = {
    "local_feature_matching": LocalFeatureMatchingAdapter(),
    "zero_shot_classification": ZeroShotClassificationAdapter(),
    "asr": ASRAdapter(),
    "sequence_labeling": SequenceLabelingAdapter(),
}

LEVEL_RANK = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def plan_benchmarks(state: TaskState, budget: ExecutionBudget | None = None) -> list[BenchmarkSpec]:
    if not state.repo_evaluation or not state.repo_evaluation.repo_dir:
        return []

    budget = budget or ExecutionBudget()
    repo_dir = Path(state.repo_evaluation.repo_dir)
    readme = read_readme(repo_dir, limit=30000)
    brief = state.reproduction_brief
    scripts = _expanded_scripts(repo_dir, state.repo_evaluation.candidate_scripts)

    task_family = classify_task_family(
        task=brief.task if brief else None,
        datasets=brief.datasets if brief else [],
        metrics=brief.metrics if brief else [],
        keywords=brief.method_keywords if brief else [],
        repo_text=readme,
        scripts=scripts,
    )
    adapter = ADAPTERS.get(task_family)
    if adapter is None:
        return []

    context = AdapterContext(
        workspace_dir=Path(state.workspace_dir),
        repo_dir=repo_dir,
        readme_text=readme,
        task=brief.task if brief else None,
        datasets=brief.datasets if brief else [],
        metrics=brief.metrics if brief else [],
        method_keywords=brief.method_keywords if brief else [],
        scripts=scripts,
        budget=budget,
        paper_slug=stable_paper_slug(state),
    )
    return adapter.propose_benchmarks(context)


def select_best_benchmark(specs: list[BenchmarkSpec], budget: ExecutionBudget | None = None) -> BenchmarkSpec | None:
    if not specs:
        return None
    budget = budget or ExecutionBudget()
    max_rank = LEVEL_RANK[budget.target_level]
    runnable = [
        spec for spec in specs
        if spec.runnable and LEVEL_RANK[spec.level] <= max_rank and not _dataset_budget_block_reason(spec, budget)
    ]
    if not runnable:
        return None
    return sorted(runnable, key=lambda spec: (LEVEL_RANK[spec.level], _spec_score(spec)), reverse=True)[0]


def downgrade_reasons(specs: list[BenchmarkSpec], selected: BenchmarkSpec | None, budget: ExecutionBudget | None = None) -> list[str]:
    budget = budget or ExecutionBudget()
    reasons: list[str] = []
    target_rank = LEVEL_RANK[budget.target_level]
    achieved_rank = LEVEL_RANK[selected.level] if selected else -1
    if achieved_rank < target_rank:
        blocked = [
            spec for spec in specs
            if LEVEL_RANK[spec.level] > achieved_rank and LEVEL_RANK[spec.level] <= target_rank
        ]
        for spec in blocked:
            reason = _dataset_budget_block_reason(spec, budget) or spec.feasibility.get("reason") or spec.fallback_reason
            if reason:
                reasons.append(f"{spec.level} {spec.title}: {reason}")
    if selected and selected.fallback_reason:
        reasons.append(selected.fallback_reason)
    return _dedupe(reasons)


def read_readme(repo_dir: Path, limit: int = 8000) -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = repo_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    return ""


def _expanded_scripts(repo_dir: Path, candidate_scripts: list[str]) -> list[str]:
    mined = mine_script_signals(repo_dir, candidate_scripts)
    scripts = [signal.path for signal in mined]
    for script in candidate_scripts:
        if script not in scripts:
            scripts.append(script)
    return scripts


def _spec_score(spec: BenchmarkSpec) -> int:
    score = 0
    if spec.reference.get("metrics"):
        score += 5
    if spec.command_kind == "official_script":
        score += 4
    if spec.command_kind == "generated_runner":
        score += 2
    score += len(spec.evidence)
    return score


def _dataset_budget_block_reason(spec: BenchmarkSpec, budget: ExecutionBudget) -> str | None:
    if budget.allow_large_downloads:
        return None

    size_gb = spec.dataset.size_gb
    if size_gb is not None:
        if size_gb > budget.max_dataset_size_gb:
            return (
                f"estimated dataset size {size_gb:.2f}GB exceeds the "
                f"{budget.max_dataset_size_gb:.2f}GB benchmark budget"
            )
        return None

    if spec.level == "L3" and spec.dataset.source not in {"bundled", "readme", "synthetic"}:
        return (
            "dataset size is unknown, so the L3 run is held until the data "
            f"footprint can be verified under {budget.max_dataset_size_gb:.2f}GB"
        )
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
