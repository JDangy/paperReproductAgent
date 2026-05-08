# Paper Reproduction Smoke Agent

Automated pipeline that takes an academic paper (PDF), locates the corresponding code repository, builds the environment, runs a smoke test, plans and executes task-family–aware benchmark reproduction, attempts a lightweight end-to-end reproduction when safe, and produces a reproducibility report.

> **Scope:** This tool targets lightweight reproduction for simple papers: it can run bundled demos, inference examples, small evaluations, or tests when they do not require training, private files, or large datasets. It also supports automated benchmark planning and execution for supported task families (local feature matching, zero-shot classification, ASR, and sequence labeling). It does **not** reproduce large-scale training or guarantee that paper metrics are numerically matched.

---

## What This Agent Can and Cannot Do

This agent is best understood as an automated **first-pass reproduction engineer**: it finds code, builds an environment, runs the safest feasible benchmark or example, parses evidence, and writes a report. It is not a full replacement for a researcher manually reproducing every table and ablation in a paper.

### It can do

- Parse a local PDF and extract metadata, task hints, datasets, metrics, method keywords, GitHub links, and benchmark protocol hints.
- Search GitHub and project pages for likely official repositories, then rerank candidates using paper links, method-name signals, README/title evidence, repository metadata, and the input PDF filename when PDF title extraction is noisy.
- Clone or copy a repository, inspect README/scripts/configs/sample files, detect risk flags, and compute a runnable score.
- Build an isolated environment with `conda`, `venv`, or Docker; the `conda` backend can install requirements, install editable packages, relax brittle pins, and perform limited dependency repair.
- Run conservative smoke tests to verify that the environment and entry point are usable.
- Plan and run task-family-aware benchmarks for:
  - local feature matching
  - zero-shot classification
  - ASR
  - sequence labeling
- Fall back from harder benchmark levels to lighter ones when a full protocol is unavailable or fails.
- Run lightweight demos, inference examples, or README examples when they are safe and self-contained.
- Prefer CUDA/GPU execution when the repository and dependencies support it.
- Parse structured metrics such as AUC, matching score, FPS/latency, Top-1/Top-5 accuracy, WER/CER, entity tags, keypoints, descriptors, and matches.
- Produce Markdown and JSON reports with final status, commands, logs, metrics, failure types, downgrade reasons, and next steps.

### It cannot guarantee

- Full training-from-scratch reproduction.
- Full reproduction of every paper table, ablation, hyperparameter setting, or large-scale benchmark.
- Access to private files, manually registered datasets, private model weights, or license-gated resources.
- Successful builds for repositories that require old compilers, custom CUDA extensions, unavailable wheels, or undocumented system packages.
- Strict numerical parity with paper results; it reports what it ran and compares available metrics, but it does not prove full equivalence.
- Correct paper understanding from every PDF. PDF extraction can be noisy, so the agent uses evidence gates and fallback rules, but manual review is still recommended for high-stakes claims.
- Safe execution of arbitrary research code without risk. Use Docker for stronger isolation, or `--backend none` for static analysis only.

### Recent conda-mode validation

The current six-paper gold set was run with `--backend conda` and GPU available. The pipeline parsed all papers, selected the correct top-1 repository for all six items, built task-local conda environments, and completed a benchmark for each item without crashing.

| Paper | Selected repo | Final status | Achieved reproduction |
|---|---|---|---|
| SuperGlue | `magicleap/SuperGluePretrainedNetwork` | `benchmark_success` | L2 official bundled pair evaluation; parsed AUC@5/10/20, Prec, MScore |
| LightGlue | `cvg/LightGlue` | `benchmark_success` | L2 CUDA speed benchmark; parsed FPS/latency variants |
| CLIP | `OpenAI/CLIP` | `benchmark_success` | L3 CIFAR-100 zero-shot benchmark; parsed Top-1/Top-5 accuracy |
| XFeat | `verlab/accelerated_features` | `benchmark_success` | L1 minimal local-feature example; parsed keypoints, descriptors, matches |
| Whisper | `openai/whisper` | `benchmark_success` | L3 LibriSpeech ASR benchmark; parsed WER/CER |
| Flair | `zalandoresearch/flair` | `benchmark_success` | L1 pretrained NER sample inference; parsed entities and tags |

Summary from that run:

```text
Paper parse success: 6/6
Correct repo (top 1): 6/6
Expected repo in top 5: 6/6
Pipeline crashed: 0/6
Backend: conda
```

These results demonstrate autonomous lightweight/benchmark reproduction, not full paper reimplementation or training-level reproduction.

---

## Quick Start

```bash
# 1. Install (requires Python >= 3.8)
pip install poetry
cd paperReproductAgent
poetry install

# 2. Configure API keys
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY (required for paper understanding)

# 3. Run against a local PDF with a conda environment
poetry run paper-smoke run --input /path/to/paper.pdf --backend conda

# 4. Or launch the interactive TUI
poetry run paper-smoke tui
```

---

## Installation

### Prerequisites

- Python >= 3.8
- Git
- Conda — recommended for local environment builds without Docker permissions
- (Optional) Docker — only needed for `--backend docker`

### Steps

```bash
git clone <repo-url> && cd paperReproductAgent/paperReproductAgent
poetry install
```

Alternatively without Poetry:

```bash
pip install pydantic pydantic-settings typer rich httpx requests \
    PyMuPDF beautifulsoup4 jinja2 python-dotenv GitPython pyyaml \
    openai textual
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | LLM API key (paper understanding, report generation) |
| `OPENAI_BASE_URL` | No | — | Custom API endpoint (e.g. DeepSeek, Azure OpenAI) |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model name for the OpenAI-compatible endpoint |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (alternative LLM backend) |
| `GITHUB_TOKEN` | No | — | GitHub personal access token (increases API rate limit) |
| `DEFAULT_WORKSPACE` | No | `./workspace` | Default workspace directory |
| `DEFAULT_BACKEND` | No | `conda` | Default execution backend: `none`, `local`, `venv`, `conda`, `docker` |
| `DEFAULT_TIMEOUT_MINUTES` | No | `30` | Timeout per pipeline step |
| `DEFAULT_MAX_REPAIR_ATTEMPTS` | No | `5` | Max automatic dependency repair attempts |
| `DEFAULT_PREFER_CPU` | No | `true` | Prefer CPU-only packages |

---

## CLI Reference

### `paper-smoke run` — Process a single paper

```bash
paper-smoke run --input /path/to/paper.pdf [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--input` (required) | — | Local PDF file path |
| `--repo` | — | Manually specify a GitHub repo URL |
| `--repo-dir` | — | Use a local repo directory instead of cloning |
| `--workspace` | `./workspace` | Output workspace directory |
| `--backend` | `conda` | `none`, `local`, `venv`, `conda`, or `docker` |
| `--timeout-minutes` | `30` | Per-step timeout |
| `--max-repair-attempts` | `5` | Max dependency repair retries (`venv` and `conda`) |

**Examples:**

```bash
# Minimal: parse paper, search GitHub, evaluate repo only (no execution)
paper-smoke run --input paper.pdf --backend none

# Full pipeline with a local conda environment (recommended when Docker is unavailable)
paper-smoke run --input paper.pdf --backend conda

# Full pipeline with virtualenv
paper-smoke run --input paper.pdf --backend venv

# Full pipeline with Docker
paper-smoke run --input paper.pdf --backend docker

# Skip search — use a known repo
paper-smoke run --input paper.pdf --repo https://github.com/user/repo

# Use a local clone (fastest iteration)
paper-smoke run --input paper.pdf --repo-dir /path/to/local/clone
```

### `paper-smoke tui` — Interactive terminal UI

```bash
paper-smoke tui [--workspace PATH] [--backend BACKEND] [--timeout-minutes N]
```

Key TUI commands:

| Command | Description |
|---|---|
| `/input <path>` | Set paper PDF path |
| `/repo <url>` | Set GitHub repo URL |
| `/repo-dir <path>` | Set local repo directory |
| `/backend <type>` | Set backend (`none`/`local`/`venv`/`conda`/`docker`) |
| `/run` | Start the pipeline |
| `/report` | View generated report |
| `/logs [env\|build\|smoke\|stderr\|stdout]` | View step logs |
| `/cancel` | Cancel running task |
| `/sessions` | List past sessions |
| `/resume <id>` | Resume a past session |
| `/plan` / `/act` | Toggle plan-only / execution mode |

### Other commands

```bash
# Inspect raw task state (JSON)
paper-smoke inspect-task --task-dir ./workspace/tasks/task_XXXXX

# Print the Markdown report
paper-smoke print-report --task-dir ./workspace/tasks/task_XXXXX

# Batch evaluation against a gold set
paper-smoke eval-goldset --gold-set examples/gold_set.json --backend none
```

---

## Pipeline Stages

```
PDF Input ──> Paper Ingest ──> Paper Understanding ──> GitHub Search
                                                         │
Report <── Simple Reproduction <── Benchmark Reproduction <── Smoke Test <── Env Build <── Repo Evaluation
```

1. **Paper Ingest** — Extract text and metadata from the PDF.
2. **Paper Understanding** — LLM-based extraction of task, datasets, metrics, method keywords, benchmark protocol, and GitHub links.
3. **GitHub Search** — Search for matching repositories (skipped if `--repo` or `--repo-dir` is provided).
4. **Repo Evaluation** — Clone the repo, scan structure, compute runnable score, detect risk flags, and collect benchmark surface signals.
5. **Environment Build** — Create an isolated environment (conda / virtualenv / Docker / none).
6. **Smoke Test** — Execute a conservative entry-point command (`--help`, demo script, or pytest) to verify the environment and entry point.
7. **Benchmark Reproduction** — Classify the paper's task family (local feature matching, zero-shot classification, ASR, sequence labeling), plan benchmark candidates via LLM review, select the highest feasible level (L0–L3), execute with automatic fallback, parse metrics, and compare against paper-reported reference values.
8. **Simple Reproduction** — When the repository appears suitable, run a non-`--help` lightweight demo / inference / evaluation command using bundled resources, and record outputs.
9. **Report** — Generate a Markdown report with final status, benchmark comparisons, and actionable next steps.

---

## Report Final Status

The `final_status` field in the report is the single most important output. Here is what each value means:

| Status | Meaning |
|---|---|
| `benchmark_success` | The benchmark reproduction stage planned and executed a task-family benchmark, parsed metrics, and compared against paper-reported values. This is the strongest automated result. |
| `reproduction_success` | A lightweight end-to-end reproduction command ran successfully. This is stronger than smoke success, but still not proof of full paper-metric parity. |
| `reproduction_success_benchmark_failed` | A lightweight reproduction command succeeded, but the stronger benchmark attempt failed. Treat the lightweight run as valid evidence and inspect the benchmark logs separately. |
| `success` | A non-trivial command (demo / pytest) ran and exited with code 0. The repo installs and its entry point works. |
| `partial_success_help_only` | Only the `--help` flag succeeded. **This is NOT a full reproduction.** It means the package is importable and the CLI responds, but no actual inference or evaluation code was executed. |
| `repo_found_but_env_failed` | The repository was found but the environment (conda/venv/Docker) could not be built — typically a dependency conflict or missing system library. |
| `repo_found_but_smoke_failed` | The environment was built, but the smoke command failed (missing weights, data, wrong arguments, etc.). |
| `repo_found_but_reproduction_failed` | The repository and environment were available, but the lightweight reproduction command failed. |
| `repo_found_but_benchmark_failed` | The benchmark reproduction stage was attempted but the benchmark command failed. |
| `repo_found_reproduction_not_run` | The repository was found, but no safe lightweight reproduction command was available. |
| `repo_found_benchmark_not_run` | The repository was found, but no runnable benchmark plan could be generated (e.g. unsupported task family, no candidate scripts). |
| `repo_found_smoke_not_run` | The repository was found and statically evaluated, but no code was executed (`--backend none`). |
| `repo_not_found` | No suitable repository was found via GitHub search or paper links. |
| `paper_parse_failed` | The PDF could not be parsed (corrupt file, scanned image, etc.). |
| `skipped_docker` | User explicitly skipped the Docker build step (legacy). |
| `failed` | An unexpected error occurred before reaching a conclusive result. |

### Important: `partial_success_help_only` != Full Reproduction

This status means the tool was only able to verify that `python script.py --help` completes successfully. While this confirms the package is importable and the CLI is functional, it does **not** verify:

- Whether inference code produces correct outputs
- Whether model weights can be downloaded
- Whether required datasets are available
- Whether numerical results match the paper

A `partial_success_help_only` result should be treated as a starting point for manual investigation, not as proof of reproducibility.

### Lightweight Reproduction Scope

The simple reproduction stage is intentionally conservative. It may run commands such as `python demo.py`, `python infer.py --input examples/sample.png`, or `pytest -q` when those commands are safe and self-contained. It blocks training-looking scripts, `--help`/version-only commands, shell metacharacters, network-looking arguments, and repositories flagged as likely requiring large datasets.

This stage is meant to fully exercise simple repositories that ship their own sample inputs or tests. If a paper requires checkpoints, large datasets, or long CUDA training, the agent should report that limitation rather than pretending the paper was reproduced.

### Benchmark Reproduction Framework

The benchmark module (`app/benchmark/`) provides automated, task-family–aware benchmark planning and execution:

1. **Task Family Classification** (`ontology.py`) — Classifies the paper into one of four supported families based on extracted keywords, datasets, and metrics:
   - **Local Feature Matching** — AUC@5/10/20, matching score, FPS (e.g. SuperPoint, LoFTR)
   - **Zero-Shot Classification** — Top-1/Top-5 accuracy (e.g. CLIP)
   - **ASR (Automatic Speech Recognition)** — WER, CER, BLEU (e.g. Whisper)
   - **Sequence Labeling** — F1, Precision, Recall (e.g. NER taggers)

2. **Benchmark Planning** (`planner.py`, `llm_planner.py`, `generic_planner.py`) — Generates candidate benchmark plans at four levels:
   - **L0** — Static analysis only (no execution)
   - **L1** — Minimal command with synthetic/tiny data
   - **L2** — Official evaluation script with small public dataset
   - **L3** — Full paper protocol with standard benchmark dataset

   Specialist adapters are evidence-gated to avoid routing noisy PDF extractions to the wrong benchmark family. Unknown task families can fall back to a generic LLM planner plus repository affordance scanning and plan validation.

3. **Execution & Fallback** (`benchmark_reproduction_agent.py`) — Executes the highest feasible plan; on failure, automatically falls back to lower levels.

4. **Metric Parsing & Comparison** (`parsers.py`, `generic_metric_parser.py`, `comparator.py`) — Extracts metric values from stdout/stderr and compares against paper-reported reference values.

5. **Adapters** (`adapters/`) — Each task family has a dedicated adapter that provides dataset metadata, metric specs, and plan templates.

---

## Project Structure

```
paperReproductAgent/
├── app/
│   ├── cli.py                    # CLI entry point (Typer)
│   ├── agents/                   # Pipeline stage agents
│   │   ├── paper_ingest_agent.py
│   │   ├── paper_understanding_agent.py
│   │   ├── github_search_agent.py
│   │   ├── repo_evaluation_agent.py
│   │   ├── conda_build_agent.py
│   │   ├── docker_build_agent.py
│   │   ├── venv_build_agent.py
│   │   ├── smoke_run_agent.py
│   │   ├── benchmark_reproduction_agent.py
│   │   ├── simple_reproduction_agent.py
│   │   ├── input_resolver_agent.py
│   │   └── report_writer_agent.py
│   ├── benchmark/                # Task-family benchmark framework
│   │   ├── adapters/             # Per-task-family adapters
│   │   │   ├── asr.py            #   ASR (WER, CER, BLEU)
│   │   │   ├── local_feature_matching.py  #   Feature matching (AUC, MScore)
│   │   │   ├── sequence_labeling.py       #   NER / tagging (F1, Precision, Recall)
│   │   │   ├── zero_shot_classification.py #   Zero-shot (Top-1, Top-5)
│   │   │   ├── downloads.py      #   Dataset download helpers
│   │   │   └── base.py           #   Adapter protocol
│   │   ├── planner.py            # Benchmark plan generation (L0–L3)
│   │   ├── llm_planner.py        # LLM-assisted plan review
│   │   ├── comparator.py         # Metric comparison against reference
│   │   ├── parsers.py            # Output metric extraction
│   │   ├── generic_metric_parser.py # LLM fallback metric parser for generic tasks
│   │   ├── generic_planner.py    # Generic benchmark planner for unknown task families
│   │   ├── plan_validator.py     # Safety/feasibility validation for generated plans
│   │   ├── repo_affordance_scanner.py # Repo scripts/configs/samples/dataset signal scanner
│   │   ├── dataset_registry.py   # Known dataset metadata
│   │   ├── ontology.py           # Task family classification
│   │   ├── schema.py             # Benchmark Pydantic models
│   │   └── script_miner.py       # Script candidate mining
│   ├── core/
│   │   ├── config.py             # Settings (loaded from .env)
│   │   ├── state.py              # Pydantic models for all pipeline data
│   │   ├── naming.py             # Stable paper slug generation
│   │   ├── paths.py              # Task directory layout
│   │   ├── file_utils.py         # JSON / state persistence
│   │   └── progress.py           # Progress event system
│   ├── tools/
│   │   ├── pdf_tool.py           # PDF text extraction (PyMuPDF)
│   │   ├── github_tool.py        # GitHub API wrapper
│   │   ├── llm.py                # OpenAI / Anthropic LLM calls
│   │   ├── arxiv_tool.py         # arXiv integration
│   │   └── network.py            # Network / proxy utilities
│   ├── templates/
│   │   └── smoke_report.md.j2    # Report Jinja2 template
│   └── tui/                      # Textual-based terminal UI
├── examples/
│   ├── gold_set.json             # Original gold set for eval-goldset
│   ├── gold_set_current_six.json # Current 6-paper gold set
│   ├── gold_set_lightweight_generalization.json
│   └── gold_set_lightweight_generalization_whisper.json
├── tests/
├── .env.example                  # Environment variable template
├── pyproject.toml                # Project metadata and dependencies
└── README.md
```

---

## Security Notes

- **API keys** are read from the `.env` file or environment variables. Never commit `.env` to version control. The `.env` file is excluded via `.gitignore`.
- **LLM calls:** Paper text is sent to the configured LLM API (OpenAI-compatible or Anthropic) for understanding and report generation. If your papers contain sensitive or proprietary data, consider using a self-hosted model via `OPENAI_BASE_URL`.
- **Code execution:** The `local`, `venv`, and `conda` backends run cloned repository code on your machine. The `conda` backend creates a task-local conda environment and is recommended when Docker is unavailable. The `docker` backend provides stronger isolation. The `none` backend performs static analysis only and executes no external code.
- **GitHub token:** Providing `GITHUB_TOKEN` increases the API rate limit for repository searches but is not required. Use a token with minimal permissions (no write access needed).
- **Network access:** The tool makes outbound HTTP requests to: GitHub API, arXiv, the configured LLM API, and PyPI (for dependency installation). No inbound ports are opened.

---

## Development

```bash
# Install dev dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Lint
poetry run ruff check app/
poetry run black --check app/
```
