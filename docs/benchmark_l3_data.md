# L3 Benchmark Data Configuration

The benchmark planner is task-family based. It does not use paper-name-specific
recipes. L3 protocols become runnable when the corresponding benchmark dataset
is available through a generic dataset entry.

By default, the planner only executes a benchmark whose dataset footprint is
known to be at most 1GB. Larger or unknown external L3 datasets remain as target
protocols in the report, but the run falls back to the highest feasible L2/L1
plan. This keeps automatic benchmark execution bounded while preserving the L3
intent and downgrade reason.

## Generic Root

You can set one root for all benchmark datasets:

```bash
export PAPER_BENCH_DATA_ROOT=/path/to/benchmark_data
```

The planner first looks for paper-named dataset cache directories. The paper
slug is derived from arXiv ID, then title, then input PDF filename. For example,
for a paper slug `clip`, the preferred layout is:

```text
$PAPER_BENCH_DATA_ROOT/clip/cifar100
./workspace/datasets/clip/cifar100
```

Legacy non-paper-named directories are still accepted for compatibility:

```text
$PAPER_BENCH_DATA_ROOT/cifar100
./workspace/datasets/cifar100
```

## Dataset-Specific Overrides

| Task family | Dataset | Env var | Size policy | Metrics |
|---|---|---|---|---|
| local_feature_matching | MegaDepth-1500 | `PAPER_BENCH_MEGDEPTH1500_DIR` | run only if configured directory is <=1GB unless large data is allowed | AUC@5/10/20, mAcc@5/10/20 |
| local_feature_matching | ScanNet-1500 | `PAPER_BENCH_SCANNET1500_DIR` | run only if configured directory is <=1GB unless large data is allowed | AUC@5/10/20, mAcc@5/10/20 |
| asr | LibriSpeech | `PAPER_BENCH_LIBRISPEECH_DIR` | test-clean scale is <=1GB; larger configured dirs fall back | WER, CER |
| sequence_labeling | CoNLL-03 | `PAPER_BENCH_CONLL03_DIR` | usually <=1GB | Precision, Recall, F1 |
| zero_shot_classification | CIFAR-100 | `PAPER_BENCH_CIFAR100_DIR` | usually <=1GB | Top-1, Top-5 |
| zero_shot_classification | ImageNet | `PAPER_BENCH_IMAGENET_DIR` | normally >1GB, so held unless large data is allowed | Top-1, Top-5 |

## Resource Controls

These optional environment variables keep L3 runs bounded:

```bash
export PAPER_BENCH_MAX_EXAMPLES=1000
export PAPER_BENCH_ASR_MODEL=tiny
export PAPER_BENCH_SEQUENCE_TAGGER_MODEL=ner
export PAPER_BENCH_CLIP_MODEL=ViT-B/32
```

The default model settings are deliberately small so the protocol can be tested
before scaling to paper-table model variants.

The default dataset-size budget is `1.0GB` via `ExecutionBudget.max_dataset_size_gb`.
Programmatic callers can opt into larger local benchmarks by setting
`ExecutionBudget.allow_large_downloads=True`.
