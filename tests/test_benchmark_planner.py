import subprocess

from app.agents.benchmark_reproduction_agent import BenchmarkReproductionAgent
from app.agents.benchmark_reproduction_agent import _is_safe_benchmark_argv
from app.benchmark.comparator import compare_metrics
from app.benchmark.parsers import parse_generic_metrics, parse_xfeat_pose_eval
from app.benchmark.planner import downgrade_reasons, plan_benchmarks, select_best_benchmark
from app.benchmark.schema import BenchmarkSpec, DatasetSpec, ExecutionBudget
from app.core.state import EnvironmentBuildResult, PaperMetadata, RepoEvaluation, ReproductionBrief, TaskState


def _state(tmp_path, repo_dir, *, task="feature matching", datasets=None, metrics=None, keywords=None, scripts=None):
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


def test_planner_selects_local_feature_matching_l2_without_repo_name(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text(
        "This repository evaluates local feature matching with AUC@5 on ScanNet.",
        encoding="utf-8",
    )
    (repo_dir / "match_pairs.py").write_text("print('AUC@5 AUC@10 AUC@20 Prec MScore')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        datasets=["ScanNet"],
        metrics=["AUC@5", "AUC@10", "matching score"],
        scripts=["match_pairs.py"],
    )

    specs = plan_benchmarks(state)
    selected = select_best_benchmark(specs)

    assert selected is not None
    assert selected.task_family == "local_feature_matching"
    assert selected.level == "L2"
    assert selected.command[:3] == ["python", "match_pairs.py", "--eval"]


def test_planner_does_not_route_noisy_superglue_brief_to_asr(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Simple Demo Repo\n\nRun python demo.py --help\n", encoding="utf-8")
    (repo_dir / "demo.py").write_text("print('Demo OK')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        task="segmentation",
        datasets=["GLUE"],
        metrics=["AUC", "IoU", "WER", "accuracy"],
        keywords=["Super-\nGlue", "Super-\nPoint", "Graph Neural Network"],
        scripts=["demo.py"],
    )

    specs = plan_benchmarks(state)

    assert specs
    assert {spec.task_family for spec in specs} == {"local_feature_matching"}


def test_local_feature_paper_protocol_estimates_known_dataset_sizes(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text(
        "Evaluation follows SuperGlue on ScanNet and PhotoTourism with AUC@5/AUC@10/AUC@20.",
        encoding="utf-8",
    )
    (repo_dir / "match_pairs.py").write_text("print('AUC@5 AUC@10 AUC@20')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        task="local feature matching",
        datasets=["ScanNet", "PhotoTourism"],
        metrics=["AUC@5", "AUC@10", "AUC@20"],
        scripts=["match_pairs.py"],
    )

    specs = plan_benchmarks(state)
    paper_spec = next(spec for spec in specs if spec.id == "local_feature_matching_paper_table_protocol")
    selected = select_best_benchmark(specs)
    reasons = downgrade_reasons(specs, selected)

    assert paper_spec.dataset.size_gb == 30.0
    assert paper_spec.dataset.name == "ScanNet-1500, PhotoTourism"
    assert any("Dataset size estimated from deterministic registry" in note for note in paper_spec.dataset.notes)
    assert any("estimated dataset size 30.00GB exceeds" in reason for reason in reasons)


def test_benchmark_agent_runs_and_parses_local_feature_table(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Local feature matching benchmark. Metrics: AUC@5 AUC@10 AUC@20.", encoding="utf-8")
    (repo_dir / "match_pairs.py").write_text("print('placeholder')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        datasets=["ScanNet"],
        metrics=["AUC@5", "AUC@10", "AUC@20"],
        scripts=["match_pairs.py"],
    )
    stdout = """
Evaluation Results (mean over 15 pairs):
AUC@5\t AUC@10\t AUC@20\t Prec\t MScore
26.99\t 48.40\t 64.47\t 73.52\t 19.60
"""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout, ""),
    )

    state = BenchmarkReproductionAgent(timeout_minutes=1).run(state)

    assert state.benchmark_run.success
    assert state.benchmark_run.achieved_level == "L2"
    assert state.benchmark_run.metrics["AUC@5"] == 26.99
    assert state.benchmark_run.comparisons[0]["status"] == "matched"
    assert state.benchmark_run.downgrade_reasons


def test_benchmark_agent_retries_lower_level_when_selected_plan_fails(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Local feature matching benchmark with FPS and keypoints.", encoding="utf-8")
    (repo_dir / "benchmark.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
    (repo_dir / "demo.py").write_text("print('keypoints: torch.Size([128, 2])')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        datasets=["sample"],
        metrics=["FPS", "AUC@5"],
        scripts=["benchmark.py", "demo.py"],
    )

    def fake_run(argv, **kwargs):
        if argv[1].endswith("benchmark.py"):
            return subprocess.CompletedProcess(argv, 1, "", "runtime dependency missing")
        return subprocess.CompletedProcess(argv, 0, "keypoints: torch.Size([128, 2])\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    state = BenchmarkReproductionAgent(timeout_minutes=1).run(state)

    assert state.benchmark_run.success
    assert state.benchmark_run.selected_spec.level == "L1"
    assert state.benchmark_run.achieved_level == "L1"
    assert state.benchmark_run.metrics["num_keypoints"] == 128
    assert any("retrying L1" in reason for reason in state.benchmark_run.downgrade_reasons)
    run_dir = tmp_path / "task" / "runs" / "benchmark_001"
    assert (run_dir / "local_feature_matching_speed_benchmark_stderr.log").exists()
    assert (run_dir / "local_feature_matching_demo_py_stdout.log").exists()
    assert (run_dir / "stdout.log").exists()


def test_planner_routes_package_style_asr_to_paper_named_librispeech_download(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "jfk.flac").write_bytes(b"fake")
    (repo_dir / "README.md").write_text(
        "Robust speech recognition model. Evaluation reports WER on LibriSpeech.",
        encoding="utf-8",
    )
    state = _state(
        tmp_path,
        repo_dir,
        task="automatic speech recognition",
        datasets=["LibriSpeech"],
        metrics=["WER"],
        keywords=["Whisper"],
        scripts=[],
    )

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.task_family == "asr"
    assert selected.level == "L3"
    assert selected.id == "asr_librispeech_eval"
    assert selected.command_kind == "generated_runner"
    assert selected.generated_script_name == "paper_benchmark_asr_librispeech.py"
    assert selected.feasibility["will_download"] is True
    assert selected.feasibility["data_source"] == str(tmp_path / "datasets" / "task-test" / "librispeech")
    assert "PAPER_BENCH_DATA_DOWNLOAD_TIMEOUT_SECONDS" in selected.generated_script_body
    assert "download_progress" in selected.generated_script_body


def test_asr_librispeech_l3_runnable_when_dataset_env_is_set(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Speech recognition benchmark reports WER on LibriSpeech.", encoding="utf-8")
    dataset_root = tmp_path / "librispeech"
    dataset_root.mkdir()
    monkeypatch.setenv("PAPER_BENCH_LIBRISPEECH_DIR", str(dataset_root))
    state = _state(
        tmp_path,
        repo_dir,
        task="automatic speech recognition",
        datasets=["LibriSpeech"],
        metrics=["WER"],
        keywords=["speech recognition"],
        scripts=[],
    )

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "asr_librispeech_eval"
    assert selected.level == "L3"
    assert selected.runnable
    assert selected.generated_script_name == "paper_benchmark_asr_librispeech.py"


def test_sequence_labeling_conll_l3_runnable_when_dataset_env_is_set(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Sequence labeling and NER benchmark on CoNLL-03.", encoding="utf-8")
    dataset_root = tmp_path / "conll03"
    dataset_root.mkdir()
    monkeypatch.setenv("PAPER_BENCH_CONLL03_DIR", str(dataset_root))
    state = _state(
        tmp_path,
        repo_dir,
        task="sequence labeling",
        datasets=["CoNLL-03"],
        metrics=["F1"],
        keywords=["NER"],
        scripts=[],
    )

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "sequence_labeling_conll03_eval"
    assert selected.level == "L3"
    assert selected.runnable
    assert selected.generated_script_name == "paper_benchmark_sequence_labeling_conll.py"


def test_sequence_labeling_conll_l3_uses_paper_named_download_cache(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Flair sequence labeling benchmark on CoNLL-03.", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        task="sequence labeling",
        datasets=["CoNLL-03"],
        metrics=["F1"],
        keywords=["Flair", "NER"],
        scripts=[],
    )
    state.paper_metadata = PaperMetadata(title="Flair")

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "sequence_labeling_conll03_eval"
    assert selected.level == "L3"
    assert selected.runnable
    assert selected.feasibility["will_download"] is True
    assert selected.feasibility["data_source"] == str(tmp_path / "datasets" / "flair" / "conll03")
    assert "PAPER_BENCH_DATA_DOWNLOAD_TIMEOUT_SECONDS" in selected.generated_script_body
    assert "download_progress" in selected.generated_script_body


def test_zero_shot_cifar100_l3_runnable_when_dataset_env_is_set(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "clip").mkdir()
    (repo_dir / "README.md").write_text("CLIP zero-shot classification benchmark on CIFAR-100.", encoding="utf-8")
    dataset_root = tmp_path / "cifar100"
    dataset_root.mkdir()
    monkeypatch.setenv("PAPER_BENCH_CIFAR100_DIR", str(dataset_root))
    state = _state(
        tmp_path,
        repo_dir,
        task="zero-shot classification",
        datasets=["CIFAR-100"],
        metrics=["Top-1 Accuracy"],
        keywords=["CLIP"],
        scripts=[],
    )

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "zero_shot_cifar100_eval"
    assert selected.level == "L3"
    assert selected.runnable
    assert selected.generated_script_name == "paper_benchmark_zero_shot_cifar100.py"


def test_zero_shot_cifar100_l3_uses_paper_named_dataset_cache(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "clip").mkdir()
    (repo_dir / "README.md").write_text("CLIP zero-shot classification benchmark on CIFAR-100.", encoding="utf-8")
    dataset_root = tmp_path / "datasets" / "clip" / "cifar100"
    dataset_root.mkdir(parents=True)
    state = _state(
        tmp_path,
        repo_dir,
        task="zero-shot classification",
        datasets=["CIFAR-100"],
        metrics=["Top-1 Accuracy"],
        keywords=["CLIP"],
        scripts=[],
    )
    state.paper_metadata = PaperMetadata(title="CLIP")

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "zero_shot_cifar100_eval"
    assert selected.level == "L3"
    assert selected.feasibility["data_source"] == str(dataset_root)


def test_planner_records_blocked_xfeat_official_eval_modules(tmp_path):
    repo_dir = tmp_path / "repo"
    eval_dir = repo_dir / "modules" / "eval"
    eval_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text(
        "Local feature matching evaluation on MegaDepth-1500 and ScanNet-1500.",
        encoding="utf-8",
    )
    (repo_dir / "minimal_example.py").write_text("print('keypoints: torch.Size([4096, 2])')\n", encoding="utf-8")
    (eval_dir / "megadepth1500.py").write_text("print('auc@5')\n", encoding="utf-8")
    (eval_dir / "scannet1500.py").write_text("print('auc@5')\n", encoding="utf-8")
    state = _state(
        tmp_path,
        repo_dir,
        task="local feature matching",
        datasets=["MegaDepth", "ScanNet"],
        metrics=["AUC@5"],
        scripts=["minimal_example.py"],
    )

    specs = plan_benchmarks(state)

    blocked = {spec.id: spec for spec in specs if spec.id.startswith("official_")}
    assert "official_megadepth1500_pose_eval" in blocked
    assert "PAPER_BENCH_MEGDEPTH1500_DIR" in blocked["official_megadepth1500_pose_eval"].feasibility["reason"]
    assert not blocked["official_megadepth1500_pose_eval"].runnable


def test_planner_makes_xfeat_megadepth_l3_runnable_when_dataset_env_is_set(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    eval_dir = repo_dir / "modules" / "eval"
    eval_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text(
        "Local feature matching evaluation on MegaDepth-1500.",
        encoding="utf-8",
    )
    (repo_dir / "minimal_example.py").write_text("print('demo')\n", encoding="utf-8")
    (eval_dir / "megadepth1500.py").write_text("print('auc@5')\n", encoding="utf-8")
    dataset_root = tmp_path / "MegaDepth1500"
    dataset_root.mkdir()
    monkeypatch.setenv("PAPER_BENCH_MEGDEPTH1500_DIR", str(dataset_root))
    state = _state(
        tmp_path,
        repo_dir,
        task="local feature matching",
        datasets=["MegaDepth"],
        metrics=["AUC@5"],
        scripts=["minimal_example.py"],
    )

    selected = select_best_benchmark(plan_benchmarks(state))

    assert selected is not None
    assert selected.id == "official_megadepth1500_pose_eval"
    assert selected.level == "L3"
    assert selected.runnable
    assert selected.command[:3] == ["python", "-m", "modules.eval.megadepth1500"]


def test_planner_keeps_l1_l2_when_l3_dataset_exceeds_size_budget():
    specs = [
        BenchmarkSpec(
            id="large_l3",
            task_family="zero_shot_classification",
            level="L3",
            title="Large ImageNet benchmark",
            dataset=DatasetSpec(name="ImageNet", source="official_repo", size_gb=144.0),
            command=["python", "eval_imagenet.py"],
        ),
        BenchmarkSpec(
            id="small_l2",
            task_family="zero_shot_classification",
            level="L2",
            title="Small bundled benchmark",
            dataset=DatasetSpec(name="bundled sample", source="bundled", size_gb=0.01),
            command=["python", "eval_sample.py"],
        ),
    ]
    budget = ExecutionBudget(max_dataset_size_gb=1.0)

    selected = select_best_benchmark(specs, budget)
    reasons = downgrade_reasons(specs, selected, budget)

    assert selected is not None
    assert selected.id == "small_l2"
    assert any("exceeds the 1.00GB benchmark budget" in reason for reason in reasons)


def test_planner_allows_large_l3_only_when_budget_opt_in_is_set():
    spec = BenchmarkSpec(
        id="large_l3",
        task_family="zero_shot_classification",
        level="L3",
        title="Large benchmark",
        dataset=DatasetSpec(name="large dataset", source="official_repo", size_gb=2.0),
        command=["python", "eval_large.py"],
    )

    selected = select_best_benchmark([spec], ExecutionBudget(max_dataset_size_gb=1.0, allow_large_downloads=True))

    assert selected is not None
    assert selected.id == "large_l3"


def test_planner_blocks_unknown_size_external_l3_until_verified():
    specs = [
        BenchmarkSpec(
            id="unknown_l3",
            task_family="asr",
            level="L3",
            title="External ASR benchmark",
            dataset=DatasetSpec(name="external ASR", source="official_repo"),
            command=["python", "eval_asr.py"],
        ),
        BenchmarkSpec(
            id="sample_l1",
            task_family="asr",
            level="L1",
            title="Sample audio",
            dataset=DatasetSpec(name="sample", source="bundled"),
            command=["python", "demo.py"],
        ),
    ]

    selected = select_best_benchmark(specs, ExecutionBudget(max_dataset_size_gb=1.0))

    assert selected is not None
    assert selected.id == "sample_l1"


def test_benchmark_safety_allows_safe_module_execution(tmp_path):
    spec = BenchmarkSpec(
        id="official_megadepth1500_pose_eval",
        task_family="local_feature_matching",
        level="L3",
        title="eval",
        dataset=DatasetSpec(name="MegaDepth-1500"),
        command=["python", "-m", "modules.eval.megadepth1500", "--dataset-dir", "data/MegaDepth"],
    )

    ok, reason = _is_safe_benchmark_argv(spec.command, [], spec)

    assert ok, reason


def test_benchmark_safety_blocks_unsafe_module_execution(tmp_path):
    spec = BenchmarkSpec(
        id="bad",
        task_family="local_feature_matching",
        level="L3",
        title="bad",
        dataset=DatasetSpec(name="x"),
        command=["python", "-m", "os.system"],
    )

    ok, _ = _is_safe_benchmark_argv(spec.command, [], spec)

    assert not ok


def test_generic_parser_extracts_xfeat_minimal_example_metrics():
    stdout = """
keypoints:  torch.Size([4096, 2])
descriptors:  torch.Size([4096, 64])
scores:  torch.Size([4096])
# detected features on each batch item: [4096, 4096, 4096, 4096]
torch.Size([146, 4])
"""

    metrics = parse_generic_metrics(stdout)

    assert metrics["num_keypoints"] == 4096
    assert metrics["descriptor_dim"] == 64
    assert metrics["batch_detected_features_mean"] == 4096
    assert metrics["num_matches"] == 146


def test_xfeat_pose_eval_parser_extracts_auc_and_macc():
    stdout = """
auc / mAcc on 1500 pairs
auc@5 :  34.1
auc@10 :  51.2
auc@20 :  68.3
mAcc@5: 44.0
mAcc@10: 61.5
mAcc@20: 78.2
"""

    metrics = parse_xfeat_pose_eval(stdout)

    assert metrics["num_pairs"] == 1500
    assert metrics["AUC@5"] == 34.1
    assert metrics["mAcc@20"] == 78.2


def test_comparator_matches_dotted_and_string_metrics():
    spec = BenchmarkSpec(
        id="clip_sample",
        task_family="zero_shot_classification",
        level="L1",
        title="clip sample",
        dataset=DatasetSpec(name="sample"),
        reference={"metrics": {"top_label": "a diagram", "label_probs.a diagram": 0.99}},
    )

    comparisons = compare_metrics(spec, {
        "top_label": "a diagram",
        "label_probs": {"a diagram": 0.991},
    })

    assert comparisons[0]["status"] == "matched"
    assert comparisons[1]["status"] == "matched"
