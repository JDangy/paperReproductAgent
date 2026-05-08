# Benchmark Planner Gold Set Report

Generated after running the benchmark-planner pipeline on the six target papers with `--backend conda`.

## Summary

| Paper | Repo correct | Final status | Target | Achieved | Task family | Selected protocol |
|---|---:|---|---:|---:|---|---|
| SuperGlue | yes | benchmark_success | L3 | L2 | local_feature_matching | Official bundled image-pair evaluation |
| LightGlue | yes | benchmark_success | L3 | L2 | local_feature_matching | Official matcher speed benchmark |
| CLIP | yes | benchmark_success | L3 | L1 | zero_shot_classification | README-style image-text zero-shot probability example |
| XFeat | yes | benchmark_success | L3 | L1 | local_feature_matching | Repository local-feature example or evaluation entry point |
| Whisper | yes | benchmark_success | L3 | L1 | asr | Bundled audio transcription sanity benchmark |
| Flair | yes | benchmark_success | L3 | L1 | sequence_labeling | Pretrained sequence tagger sample inference |

Repository discovery was correct for all six papers. No pipeline run crashed. All benchmark runs used the conda backend; each successful benchmark run reported CUDA execution where the generated runner or official script exposed device information.

## Per-Paper Results

### SuperGlue

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_core3/runs/tasks/task_20260507_150636_986503/report/reproduction_smoke_report.md)
- Achieved: L2
- Protocol: official bundled image-pair evaluation
- Metrics:
  - AUC@5: 23.58
  - AUC@10: 42.50
  - AUC@20: 61.28
  - Prec: 73.60
  - MScore: 19.64
- Downgrade reason: full paper-table local feature matching protocol requires external full benchmark data and exact paper-table protocol extraction.
- Note: AUC@5 and AUC@10 differed from the README sample reference; AUC@20, precision, and matching score were close or matched.

### LightGlue

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_core3/runs/tasks/task_20260507_151032_037483/report/reproduction_smoke_report.md)
- Achieved: L2
- Protocol: official matcher speed benchmark
- Example metrics:
  - LightGlue-adaptive easy 512: 68.49 FPS
  - LightGlue-adaptive easy 1024: 85.47 FPS
  - LightGlue-adaptive difficult 512: 53.19 FPS
  - LightGlue-adaptive difficult 1024: 53.76 FPS
- Downgrade reason: full paper-table local feature matching protocol requires external datasets and reference extraction.
- Note: speed numbers are hardware/config dependent and should not be judged by strict parity unless hardware and settings match.

### CLIP

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_core3/runs/tasks/task_20260507_151438_415848/report/reproduction_smoke_report.md)
- Achieved: L1
- Protocol: README-style image-text zero-shot probability example
- Metrics:
  - device: cuda
  - model: ViT-B/32
  - top_label: a diagram
  - top_probability: 0.99267578125
- Downgrade reason: full zero-shot classification benchmark data, such as ImageNet/CIFAR protocol, is not bundled.

### XFeat

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_general3/runs/tasks/task_20260507_152138_262806/report/reproduction_smoke_report.md)
- Achieved: L1
- Protocol: repository local-feature example or evaluation entry point
- Reparsed sanity metrics after parser refinement:
  - num_keypoints: 4096
  - descriptor_dim: 64
  - batch_detected_features_mean: 4096
  - num_matches: 146
- Downgrade reason: official MegaDepth-1500 and ScanNet-1500 evaluation modules exist, but require external dataset paths.

### Whisper

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_general3/runs/tasks/task_20260507_152525_306635/report/reproduction_smoke_report.md)
- Achieved: L1
- Protocol: bundled audio transcription sanity benchmark
- Metrics:
  - device: cuda
  - model: tiny
  - audio: tests/jfk.flac
  - language: en
  - text: "And so my fellow Americans ask not what your country can do for you ask what you can do for your country."
- Downgrade reason: full ASR benchmark references/datasets are not bundled.

### Flair

- Report: [reproduction_smoke_report.md](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_general3/runs/tasks/task_20260507_152845_647688/report/reproduction_smoke_report.md)
- Achieved: L1
- Protocol: pretrained sequence tagger sample inference
- Metrics:
  - device: cuda
  - model: ner
  - sentence: George Washington went to Washington.
  - num_entities: 2
  - entities: George Washington/PER, Washington/LOC
- Downgrade reason: full sequence-labeling benchmark data/protocol, such as CoNLL-style F1 evaluation, is not bundled.

## Result Directories

- Core set: [goldset_results_benchmark_planner_v1_core3](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_core3)
- Generalization set: [goldset_results_benchmark_planner_v1_general3](/home/duyuan/agent/paperReproductAgent/goldset_results_benchmark_planner_v1_general3)

## Verification

```text
/home/duyuan/miniconda3/envs/torch_py39_env/bin/python -m pytest -q
107 passed, 5 warnings
```
