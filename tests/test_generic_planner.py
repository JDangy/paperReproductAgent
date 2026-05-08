"""Tests for the generic benchmark planner, repo affordance scanner,
plan validator, and generic metric parser."""

import json
from pathlib import Path

import pytest

from app.benchmark.generic_metric_parser import parse_with_llm_fallback
from app.benchmark.generic_planner import GenericLLMBenchmarkPlanner, _parse_candidate
from app.benchmark.ontology import (
    classify_task_family,
    classify_task_ontology,
    metric_specs_for_family,
)
from app.benchmark.parsers import parse_metrics
from app.benchmark.plan_validator import BenchmarkPlanValidator
from app.benchmark.planner import plan_benchmarks
from app.benchmark.repo_affordance_scanner import RepoAffordance, scan_repo_affordances
from app.benchmark.schema import (
    BenchmarkSpec,
    DatasetSpec,
    ExecutionBudget,
    MetricSpec,
    TaskOntology,
    KNOWN_TASK_FAMILIES,
)
from app.core.state import EnvironmentBuildResult, RepoEvaluation, ReproductionBrief, TaskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(tmp_path, repo_dir, *, task="object detection", datasets=None, metrics=None, keywords=None, scripts=None):
    task_dir = tmp_path / "task"
    task_dir.mkdir(exist_ok=True)
    return TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="local",
        env_build=EnvironmentBuildResult(build_success=True),
        reproduction_brief=ReproductionBrief(
            task=task,
            datasets=datasets or [],
            metrics=metrics or [],
            method_keywords=keywords or [],
        ),
        repo_evaluation=RepoEvaluation(
            repo_dir=str(repo_dir),
            candidate_scripts=scripts or [],
        ),
    )


def _make_repo(tmp_path, *, readme="", scripts=None, configs=None, samples=None):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(exist_ok=True)
    if readme:
        (repo_dir / "README.md").write_text(readme, encoding="utf-8")
    for name, body in (scripts or {}).items():
        path = repo_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    for name, body in (configs or {}).items():
        path = repo_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    for name, body in (samples or {}).items():
        path = repo_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body if isinstance(body, bytes) else body.encode())
    return repo_dir


# ---------------------------------------------------------------------------
# Repo affordance scanner
# ---------------------------------------------------------------------------

class TestRepoAffordanceScanner:

    def test_discovers_entrypoints(self, tmp_path):
        repo_dir = _make_repo(tmp_path, scripts={
            "eval.py": "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('--weights')\nprint('evaluate')",
            "demo.py": "# Demo script\nprint('hello')",
        })
        affordances = scan_repo_affordances(repo_dir, "", ["eval.py", "demo.py"])

        paths = {e.path for e in affordances.entrypoints}
        assert "eval.py" in paths or "demo.py" in paths
        ep = next(e for e in affordances.entrypoints if e.path == "eval.py")
        assert "--weights" in ep.cli_args

    def test_discovers_configs(self, tmp_path):
        repo_dir = _make_repo(tmp_path, configs={
            "configs/eval.yaml": "model: resnet50\ndataset: coco\nbatch_size: 4",
        })
        affordances = scan_repo_affordances(repo_dir, "", [])

        paths = {c.path for c in affordances.configs}
        assert any("eval.yaml" in p for p in paths)
        cfg = next(c for c in affordances.configs if "eval.yaml" in c.path)
        assert "model" in cfg.keys

    def test_discovers_sample_files(self, tmp_path):
        repo_dir = _make_repo(tmp_path, samples={
            "demo/test.jpg": b"\xff\xd8\xff\xe0",
            "demo/audio.wav": b"RIFF",
        })
        affordances = scan_repo_affordances(repo_dir, "", [])

        paths = {s.path for s in affordances.sample_files}
        assert any("test.jpg" in p for p in paths)
        assert any("audio.wav" in p for p in paths)

    def test_discovers_dataset_mentions_from_readme(self, tmp_path):
        readme = "We evaluate on COCO and ImageNet using mAP."
        repo_dir = _make_repo(tmp_path, readme=readme)
        affordances = scan_repo_affordances(repo_dir, readme, [])

        names = {d.name for d in affordances.dataset_mentions}
        assert "COCO" in names
        assert "ImageNet" in names

    def test_discovers_framework_signals(self, tmp_path):
        readme = "Built with PyTorch and HuggingFace Transformers."
        repo_dir = _make_repo(tmp_path, readme=readme)
        affordances = scan_repo_affordances(repo_dir, readme, [])

        assert "pytorch" in affordances.framework_signals
        assert "huggingface" in affordances.framework_signals

    def test_handles_empty_repo(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        affordances = scan_repo_affordances(repo_dir, "", [])

        assert affordances.entrypoints == []
        assert affordances.configs == []
        assert affordances.sample_files == []


# ---------------------------------------------------------------------------
# Plan validator
# ---------------------------------------------------------------------------

class TestBenchmarkPlanValidator:

    def test_blocks_missing_scripts(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test_1",
            task_family="object_detection",
            level="L1",
            title="missing script",
            dataset=DatasetSpec(name="sample"),
            command=["python", "nonexistent.py"],
        )

        validator = BenchmarkPlanValidator(repo_dir, [])
        result = validator.validate_single(spec)

        assert result.feasibility.get("runnable") is False

    def test_blocks_shell_metacharacters(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test_2",
            task_family="object_detection",
            level="L1",
            title="shell injection",
            dataset=DatasetSpec(name="sample"),
            command=["python", "eval.py", "; rm -rf /"],
        )

        validator = BenchmarkPlanValidator(repo_dir, ["eval.py"])
        result = validator.validate_single(spec)

        assert result.feasibility.get("runnable") is False

    def test_blocks_training_commands(self, tmp_path):
        repo_dir = _make_repo(tmp_path, scripts={"train.py": "print('train')"})
        spec = BenchmarkSpec(
            id="test_3",
            task_family="object_detection",
            level="L3",
            title="training blocked",
            dataset=DatasetSpec(name="sample"),
            command=["python", "train.py"],
        )

        validator = BenchmarkPlanValidator(repo_dir, ["train.py"])
        result = validator.validate_single(spec)

        assert result.feasibility.get("runnable") is False

    def test_blocks_unsafe_generated_script(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test_4",
            task_family="object_detection",
            level="L1",
            title="bad script",
            dataset=DatasetSpec(name="sample"),
            command=[],
            generated_script_name="bench.py",
            generated_script_body="import os\nos.system('rm -rf /')",
        )

        validator = BenchmarkPlanValidator(repo_dir, [])
        result = validator.validate_single(spec)

        assert result.feasibility.get("runnable") is False

    def test_allows_safe_command(self, tmp_path):
        repo_dir = _make_repo(tmp_path, scripts={"eval.py": "print('eval')"})
        spec = BenchmarkSpec(
            id="test_5",
            task_family="object_detection",
            level="L1",
            title="safe eval",
            dataset=DatasetSpec(name="sample", source="bundled"),
            command=["python", "eval.py", "--config", "config.yaml"],
        )

        validator = BenchmarkPlanValidator(repo_dir, ["eval.py"])
        result = validator.validate_single(spec)

        assert result.feasibility.get("runnable") is not False

    def test_deduplicates_ids(self, tmp_path):
        repo_dir = _make_repo(tmp_path, scripts={"eval.py": "print('eval')"})
        specs = [
            BenchmarkSpec(id="dup", task_family="x", level="L0", title="a", dataset=DatasetSpec(name="s"), feasibility={"runnable": False}),
            BenchmarkSpec(id="dup", task_family="x", level="L0", title="b", dataset=DatasetSpec(name="s"), feasibility={"runnable": False}),
        ]

        validator = BenchmarkPlanValidator(repo_dir, ["eval.py"])
        result = validator.validate(specs)

        # Second spec with same id should be marked non-runnable due to duplication
        assert result[1].feasibility.get("runnable") is False
        assert result[1].feasibility.get("reason") is not None or "duplicate" in str(result[1].feasibility)


# ---------------------------------------------------------------------------
# Generic planner response parsing
# ---------------------------------------------------------------------------

class TestGenericPlannerParsing:

    def test_parse_valid_candidate(self):
        item = {
            "level": "L1",
            "title": "Demo inference",
            "command": ["python", "demo.py", "--image", "test.jpg"],
            "command_kind": "official_script",
            "dataset": {"name": "sample", "source": "bundled"},
            "model": {"name": "resnet50"},
            "expected_metrics": [
                {"name": "mAP", "direction": "higher_is_better", "unit": "%"},
            ],
            "parser": {"type": "generic_metrics"},
            "feasibility": {"runnable": True},
            "evidence": ["found demo.py"],
        }

        spec = _parse_candidate(item, "object_detection", 0)

        assert spec is not None
        assert spec.level == "L1"
        assert spec.task_family == "object_detection"
        assert spec.command == ["python", "demo.py", "--image", "test.jpg"]
        assert len(spec.expected_metrics) == 1
        assert spec.expected_metrics[0].name == "mAP"

    def test_parse_candidate_with_string_command(self):
        item = {
            "level": "L0",
            "title": "Help",
            "command": "python tools/test.py --help",
        }
        spec = _parse_candidate(item, "unknown", 0)

        assert spec is not None
        assert spec.command == ["python", "tools/test.py", "--help"]

    def test_parse_invalid_candidate_returns_none(self):
        # Passing a non-dict should return None gracefully
        spec = _parse_candidate("not a dict", "x", 0)
        assert spec is None


# ---------------------------------------------------------------------------
# Generic planner end-to-end (with mocked LLM)
# ---------------------------------------------------------------------------

class TestGenericPlannerIntegration:

    def test_returns_specs_when_llm_responds(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path, scripts={
            "tools/test.py": "import argparse\nparser=argparse.ArgumentParser()\nparser.add_argument('--config')\nprint('mAP=41.7')",
            "demo/demo.py": "print('demo')",
        }, readme="Object detection with mAP on COCO.", samples={
            "demo/test.jpg": b"\xff\xd8\xff\xe0",
        })

        mock_response = {
            "candidates": [
                {
                    "level": "L1",
                    "title": "Demo inference on sample",
                    "command": ["python", "demo/demo.py"],
                    "command_kind": "official_script",
                    "dataset": {"name": "sample", "source": "bundled", "size_estimate": "tiny", "size_gb": 0.001},
                    "model": {"name": None, "checkpoint_source": "unknown"},
                    "expected_metrics": [],
                    "parser": {"type": "generic_metrics"},
                    "feasibility": {"runnable": True},
                    "evidence": ["demo.py exists"],
                },
            ],
        }
        monkeypatch.setattr(
            "app.benchmark.generic_planner.call_llm_json",
            lambda **kwargs: mock_response,
        )

        from app.benchmark.adapters.base import AdapterContext
        from app.benchmark.repo_affordance_scanner import scan_repo_affordances

        context = AdapterContext(
            workspace_dir=tmp_path,
            repo_dir=repo_dir,
            readme_text="Object detection with mAP on COCO.",
            task="object detection",
            datasets=["COCO"],
            metrics=["mAP"],
            method_keywords=[],
            scripts=["tools/test.py", "demo/demo.py"],
            budget=ExecutionBudget(),
            paper_slug="test",
        )
        affordances = scan_repo_affordances(repo_dir, "Object detection with mAP on COCO.", ["tools/test.py", "demo/demo.py"])
        planner = GenericLLMBenchmarkPlanner()
        specs = planner.propose_benchmarks(context, affordances, "object_detection", None)

        assert len(specs) == 1
        assert specs[0].level == "L1"
        assert specs[0].task_family == "object_detection"

    def test_returns_empty_when_llm_unavailable(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path)
        monkeypatch.setattr(
            "app.benchmark.generic_planner.call_llm_json",
            lambda **kwargs: None,
        )

        from app.benchmark.adapters.base import AdapterContext

        context = AdapterContext(
            workspace_dir=tmp_path, repo_dir=repo_dir,
            readme_text="", task=None, datasets=[], metrics=[],
            method_keywords=[], scripts=[], budget=ExecutionBudget(),
            paper_slug="test",
        )
        planner = GenericLLMBenchmarkPlanner()
        specs = planner.propose_benchmarks(context, RepoAffordance(), "unknown", None)

        assert specs == []


# ---------------------------------------------------------------------------
# Generic metric parser
# ---------------------------------------------------------------------------

class TestGenericMetricParser:

    def test_falls_back_to_regex_first(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="object_detection",
            level="L1",
            title="test",
            dataset=DatasetSpec(name="sample"),
            parser={"type": "generic_metrics"},
        )

        metrics = parse_with_llm_fallback(
            spec,
            "mAP: 41.7\nFPS: 30.5\n",
            "",
            repo_dir,
            tmp_path,
        )
        # parse_generic_metrics should catch FPS
        assert "FPS" in metrics

    def test_calls_llm_when_regex_empty(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="object_detection",
            level="L2",
            title="test",
            dataset=DatasetSpec(name="COCO"),
            expected_metrics=[MetricSpec(name="mAP", direction="higher_is_better")],
            parser={},
        )

        mock_llm = {"metrics": {"mAP": 41.7}, "confidence": 0.9}
        monkeypatch.setattr(
            "app.benchmark.generic_metric_parser.call_llm_json",
            lambda **kwargs: mock_llm,
        )

        metrics = parse_with_llm_fallback(
            spec,
            "Average Precision  (AP) @[ IoU=0.50:0.95 ] = 0.417",
            "",
            repo_dir,
            tmp_path,
        )
        assert "mAP" in metrics
        assert metrics["mAP"] == 41.7

    def test_returns_empty_when_all_fail(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="unknown",
            level="L0",
            title="test",
            dataset=DatasetSpec(name="sample"),
            parser={},
        )
        monkeypatch.setattr(
            "app.benchmark.generic_metric_parser.call_llm_json",
            lambda **kwargs: None,
        )

        metrics = parse_with_llm_fallback(spec, "no metrics here", "", repo_dir, tmp_path)
        assert metrics == {}


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------

class TestTaskOntology:

    def test_classifies_known_family(self):
        ontology = classify_task_ontology(
            task="local feature matching",
            datasets=["ScanNet"],
            metrics=["AUC@5"],
            keywords=[],
            repo_text="",
            scripts=[],
        )
        assert ontology.family == "local_feature_matching"
        assert ontology.is_known_family is True

    def test_classifies_unknown_family(self):
        ontology = classify_task_ontology(
            task="object detection",
            datasets=["COCO"],
            metrics=["mAP"],
            keywords=["YOLO"],
            repo_text="",
            scripts=[],
        )
        assert ontology.family != "local_feature_matching"
        assert ontology.is_known_family is False

    def test_backward_compat_classify_task_family(self):
        result = classify_task_family(
            task="speech recognition",
            datasets=["LibriSpeech"],
            metrics=["WER"],
            keywords=["Whisper"],
            repo_text="",
            scripts=[],
        )
        assert result == "asr"

    def test_metric_specs_for_known_family(self):
        specs = metric_specs_for_family("asr")
        names = [s.name for s in specs]
        assert "WER" in names

    def test_metric_specs_inferred_from_paper_metrics(self):
        specs = metric_specs_for_family("object_detection", metrics=["mAP", "AP50", "FPS"])
        assert len(specs) == 3
        assert specs[0].name == "mAP"
        assert specs[0].direction == "higher_is_better"
        # FPS should not be lower_is_better
        fps = next(s for s in specs if s.name == "FPS")
        assert fps.direction == "higher_is_better"

    def test_infer_domain_cv(self):
        ontology = classify_task_ontology(
            task="image segmentation",
            datasets=["COCO"],
            metrics=["mIoU"],
            keywords=[],
            repo_text="",
            scripts=[],
        )
        assert ontology.domain == "cv"
        assert "image" in ontology.input_modalities

    def test_infer_domain_nlp(self):
        ontology = classify_task_ontology(
            task="machine translation",
            datasets=["WMT"],
            metrics=["BLEU"],
            keywords=[],
            repo_text="",
            scripts=[],
        )
        assert ontology.domain == "nlp"
        assert "text" in ontology.input_modalities


# ---------------------------------------------------------------------------
# Planner integration — generic fallback for unknown task families
# ---------------------------------------------------------------------------

class TestPlannerGenericFallback:

    def test_plan_benchmarks_returns_specs_for_unknown_task(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path, scripts={
            "tools/test.py": "import argparse\nparser=argparse.ArgumentParser()\nprint('eval')",
        }, readme="YOLO object detection on COCO with mAP evaluation.")

        mock_response = {
            "candidates": [
                {
                    "level": "L0",
                    "title": "Check eval script",
                    "command": ["python", "tools/test.py", "--help"],
                    "command_kind": "official_script",
                    "dataset": {"name": "none", "source": "synthetic"},
                    "feasibility": {"runnable": True},
                    "evidence": ["tools/test.py exists"],
                },
            ],
        }
        monkeypatch.setattr(
            "app.benchmark.generic_planner.call_llm_json",
            lambda **kwargs: mock_response,
        )

        state = _state(
            tmp_path, repo_dir,
            task="object detection",
            datasets=["COCO"],
            metrics=["mAP"],
            scripts=["tools/test.py"],
        )
        specs = plan_benchmarks(state)

        assert len(specs) >= 1
        assert specs[0].task_family not in KNOWN_TASK_FAMILIES

    def test_plan_benchmarks_prefers_specialist_for_known_family(self, tmp_path):
        repo_dir = _make_repo(tmp_path, readme="Local feature matching with AUC@5 on ScanNet.", scripts={
            "match_pairs.py": "print('AUC@5 AUC@10 AUC@20 Prec MScore')\n",
        })

        state = _state(
            tmp_path, repo_dir,
            task="feature matching",
            datasets=["ScanNet"],
            metrics=["AUC@5"],
            scripts=["match_pairs.py"],
        )
        specs = plan_benchmarks(state)

        # Should use specialist adapter, not generic planner
        assert any(s.task_family == "local_feature_matching" for s in specs)

    def test_plan_benchmarks_generic_validates_commands(self, tmp_path, monkeypatch):
        repo_dir = _make_repo(tmp_path)

        # LLM proposes a command referencing a non-existent script
        mock_response = {
            "candidates": [
                {
                    "level": "L1",
                    "title": "Run missing script",
                    "command": ["python", "nonexistent_eval.py"],
                    "command_kind": "official_script",
                    "dataset": {"name": "sample", "source": "bundled"},
                    "feasibility": {"runnable": True},
                },
            ],
        }
        monkeypatch.setattr(
            "app.benchmark.generic_planner.call_llm_json",
            lambda **kwargs: mock_response,
        )

        state = _state(tmp_path, repo_dir, task="unknown task", scripts=[])
        specs = plan_benchmarks(state)

        # The spec should exist but be marked as non-runnable
        assert len(specs) == 1
        assert specs[0].feasibility.get("runnable") is False


# ---------------------------------------------------------------------------
# Parsers fallback for unknown task families
# ---------------------------------------------------------------------------

class TestParsersFallback:

    def test_parse_metrics_tries_generic_for_unknown_family(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="object_detection",
            level="L1",
            title="test",
            dataset=DatasetSpec(name="sample"),
            parser={},  # no specific parser type
        )

        metrics = parse_metrics(spec, "FPS: 25.3\nAccuracy: 0.92\n", "", repo_dir, tmp_path)
        assert "FPS" in metrics or "Accuracy" in metrics

    def test_parse_metrics_extracts_cv_metrics_for_unknown_family(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="computer_vision_detection",
            level="L1",
            title="test",
            dataset=DatasetSpec(name="sample"),
            parser={"type": "generic_metrics"},
        )

        metrics = parse_metrics(spec, "mAP: 41.7\nAP50: 62.3\nmIoU: 55.1\n", "", repo_dir, tmp_path)
        assert metrics["mAP"] == 41.7
        assert metrics["AP50"] == 62.3
        assert metrics["mIoU"] == 55.1

    def test_parse_metrics_uses_specialist_for_known_family(self, tmp_path):
        repo_dir = _make_repo(tmp_path)
        spec = BenchmarkSpec(
            id="test",
            task_family="local_feature_matching",
            level="L2",
            title="test",
            dataset=DatasetSpec(name="sample"),
            parser={"type": "generic_metrics"},
        )

        metrics = parse_metrics(spec, "FPS: 25.3\n", "", repo_dir, tmp_path)
        assert "FPS" in metrics
