# Paper Reproduction Smoke Agent

Automated pipeline that takes an academic paper (PDF), locates the corresponding code repository, builds the environment, runs a smoke test, and produces a reproducibility report.

> **Scope:** This tool performs a *smoke test* (can the repo be installed and its entry-point script executed?) — it does **not** verify numerical results, reproduce training, or confirm paper claims.

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

# 3. Run against a local PDF
poetry run paper-smoke run --input /path/to/paper.pdf

# 4. Or launch the interactive TUI
poetry run paper-smoke tui
```

---

## Installation

### Prerequisites

- Python >= 3.8
- Git
- (Optional) Docker — needed for `--backend docker`

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
| `DEFAULT_BACKEND` | No | `venv` | Default execution backend: `none`, `local`, `venv`, `docker` |
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
| `--backend` | `venv` | `none`, `local`, `venv`, or `docker` |
| `--timeout-minutes` | `30` | Per-step timeout |
| `--max-repair-attempts` | `5` | Max dependency repair retries (venv only) |

**Examples:**

```bash
# Minimal: parse paper, search GitHub, evaluate repo only (no execution)
paper-smoke run --input paper.pdf --backend none

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
| `/backend <type>` | Set backend (`none`/`local`/`venv`/`docker`) |
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
                     Report <── Smoke Test <── Env Build <── Repo Evaluation
```

1. **Paper Ingest** — Extract text and metadata from the PDF.
2. **Paper Understanding** — LLM-based extraction of task, datasets, metrics, method keywords, and GitHub links.
3. **GitHub Search** — Search for matching repositories (skipped if `--repo` or `--repo-dir` is provided).
4. **Repo Evaluation** — Clone the repo, scan structure, compute runnable score, detect risk flags.
5. **Environment Build** — Create an isolated environment (Docker / virtualenv / none).
6. **Smoke Test** — Execute an entry-point command (`--help`, demo script, or pytest).
7. **Report** — Generate a Markdown report with final status and actionable next steps.

---

## Report Final Status

The `final_status` field in the report is the single most important output. Here is what each value means:

| Status | Meaning |
|---|---|
| `success` | A non-trivial command (demo / pytest) ran and exited with code 0. The repo installs and its entry point works. |
| `partial_success_help_only` | Only the `--help` flag succeeded. **This is NOT a full reproduction.** It means the package is importable and the CLI responds, but no actual inference or evaluation code was executed. |
| `repo_found_but_env_failed` | The repository was found but the environment (Docker/venv) could not be built — typically a dependency conflict or missing system library. |
| `repo_found_but_smoke_failed` | The environment was built, but the smoke command failed (missing weights, data, wrong arguments, etc.). |
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
│   │   ├── docker_build_agent.py
│   │   ├── venv_build_agent.py
│   │   ├── smoke_run_agent.py
│   │   └── report_writer_agent.py
│   ├── core/
│   │   ├── config.py             # Settings (loaded from .env)
│   │   ├── state.py              # Pydantic models for all pipeline data
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
│   └── gold_set.json             # Benchmark gold set for eval-goldset
├── .env.example                  # Environment variable template
├── pyproject.toml                # Project metadata and dependencies
└── README.md
```

---

## Security Notes

- **API keys** are read from the `.env` file or environment variables. Never commit `.env` to version control. The `.env` file is excluded via `.gitignore`.
- **LLM calls:** Paper text is sent to the configured LLM API (OpenAI-compatible or Anthropic) for understanding and report generation. If your papers contain sensitive or proprietary data, consider using a self-hosted model via `OPENAI_BASE_URL`.
- **Code execution:** The `local` and `venv` backends run cloned repository code on your machine. The `docker` backend provides stronger isolation. The `none` backend performs static analysis only and executes no external code.
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
