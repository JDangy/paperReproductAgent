你现在这个实现已经具备了 v0.1 的核心闭环：

```text
paper → brief → repo → evaluation → docker → smoke run → report
```

下一步迭代重点不应该是“让它更像智能体”，而应该是：

```text
让结果更可信
让失败更可解释
让测试覆盖更多真实 repo
让 Docker / LLM 行为可控
让每次运行可以量化比较
```

我建议按下面路线升级。

---

# 总体迭代方向

## 当前版本定位

你现在的架构是：

```text
线性 pipeline + deterministic tools + optional LLM enhancement
```

这是对的。

不要急着改成：

```text
多 agent 对话
自动循环修复
无限 tool-calling
```

论文复现 smoke test 的核心不是“多聪明”，而是：

```text
稳定地判断这个 repo 到底卡在哪一步
```

所以后续升级应该围绕四个能力：

1. **Benchmark**：知道它在多少论文上能成功。
2. **Diagnosis**：失败时能准确归因。
3. **Safety**：不会乱跑危险命令、不会污染环境。
4. **Control**：用户能指定 backend、repo、timeout、LLM、Docker 策略。

---

# 第一优先级：做 Evaluation Harness

这是最重要的下一步。

你现在有流水线，但还不知道：

```text
GitHub 搜索准不准？
Docker 构建失败主要因为什么？
Smoke command 选得对不对？
LLM 对结果有没有实际帮助？
```

所以要先加一个评估框架。

## 新增 `examples/gold_set.json`

格式建议：

```json
[
  {
    "name": "superglue",
    "input": "https://arxiv.org/abs/1911.11763",
    "expected_repo": "https://github.com/magicleap/SuperGluePretrainedNetwork",
    "expected_scripts": ["demo_superglue.py", "match_pairs.py"],
    "requires_training": false,
    "expected_min_status": "partial_success_help_only",
    "notes": "Inference-only repo, good smoke test target"
  }
]
```

字段建议包括：

```text
name
input
expected_repo
expected_scripts
requires_training
requires_gpu
expected_min_status
known_failure_reason
```

## 新增命令

```bash
paper-smoke eval-goldset \
  --gold-set examples/gold_set.json \
  --backend docker \
  --max-items 10
```

输出：

```text
goldset_results/
├── summary.json
├── summary.md
└── runs/
    ├── superglue/
    ├── ...
```

## 评估指标

先别搞复杂，就统计这些：

```text
paper_parse_success_rate
repo_discovery_accuracy
repo_scan_success_rate
docker_build_success_rate
smoke_command_found_rate
smoke_success_rate
partial_success_rate
report_generated_rate
```

示例输出：

```text
Gold set summary:

Papers: 10
Paper parse success: 10/10
Correct repo selected: 7/10
Docker build success: 4/10
Smoke command selected: 8/10
Smoke ran successfully: 3/10
Report generated: 10/10
```

这个会立刻告诉你下一步该优化哪里。

---

# 第二优先级：把 backend 做成明确策略

你现在 pipeline 默认进 Docker。建议改成三种 backend：

```text
none
local
docker
```

## backend=none

只做：

```text
paper ingest
paper understanding
repo search
repo evaluation
smoke command selection
report
```

不执行代码，不构建环境。

适合快速评估 repo。

```bash
paper-smoke run \
  --input https://arxiv.org/abs/1911.11763 \
  --repo-dir ./SuperGluePretrainedNetwork \
  --backend none
```

报告状态：

```text
repo_found_smoke_not_run
```

## backend=local

在当前 Python / conda 环境中只运行安全命令：

```bash
python demo.py --help
pytest -q
```

不自动 pip install。

```bash
paper-smoke run \
  --input https://arxiv.org/abs/1911.11763 \
  --repo-dir ./SuperGluePretrainedNetwork \
  --backend local
```

## backend=docker

当前已有逻辑，继续保留。

```bash
paper-smoke run \
  --input https://arxiv.org/abs/1911.11763 \
  --repo-dir ./SuperGluePretrainedNetwork \
  --backend docker
```

## 为什么这很重要

现在你的 Docker build 可能会成为最大失败源。很多时候用户只是想知道：

```text
这个 repo 看起来能不能跑？
入口脚本是什么？
依赖文件在哪里？
```

不一定每次都要 build Docker。

所以 backend 拆开后，工具会更实用。

---

# 第三优先级：加强 Repo Discovery 的可解释性

你现在的搜索策略已经不错：

```text
paper GitHub links
arXiv ID search
title search
method keyword search
```

下一步重点不是“搜更多”，而是让选择更可验证。

## 给每个候选 repo 保存完整 evidence

新增模型：

```python
class RepoEvidence(BaseModel):
    readme_contains_title: bool = False
    readme_contains_arxiv_id: bool = False
    repo_name_matches_method: bool = False
    owner_matches_author: bool = False
    is_archived: bool = False
    is_fork: bool = False
    stars: int | None = None
    pushed_at: str | None = None
    readme_excerpt: str | None = None
```

然后 `RepoCandidate` 里加：

```python
evidence: RepoEvidence | None = None
```

报告中显示：

```text
Why this repo was selected:
- Found in paper text
- README contains arXiv ID
- Repo name matches method keyword
- Not archived
```

这样用户不会觉得 agent 是黑箱乱选。

## 增加候选列表报告

不要只报告 selected repo。报告 top 5：

```text
Top repo candidates:

1. magicleap/SuperGluePretrainedNetwork
   score: 90
   reason: README contains title + arXiv ID

2. some-fork/SuperGlue
   score: 52
   reason: title search match, but fork

3. student/SuperGlue-reproduce
   score: 35
   reason: title search match only
```

这对调试 GitHubSearchAgent 特别重要。

---

# 第四优先级：Smoke Command Selection 要独立评估

你现在的 SmokeRunAgent 已经支持 LLM 推荐 + 启发式降级。下一步要把“选命令”和“执行命令”拆开。

现在大概是：

```text
SmokeRunAgent:
  select command
  safety check
  docker run
```

建议拆成：

```text
SmokeCommandSelectionAgent
SmokeRunAgent
```

或者至少内部产出一个独立 artifact：

```text
runs/smoke_command_candidates.json
```

内容：

```json
[
  {
    "command": "python demo_superglue.py --help",
    "source": "heuristic",
    "score": 90,
    "safe": true,
    "reason": "demo-like script with --help"
  },
  {
    "command": "python match_pairs.py --help",
    "source": "heuristic",
    "score": 80,
    "safe": true,
    "reason": "matching/eval-like script"
  }
]
```

这样你可以单独评估：

```text
命令选错了？
还是命令选对了但环境失败？
还是环境成功但 repo 自己报错？
```

这是 smoke agent 变成熟的关键。

---

# 第五优先级：Docker 构建不要急着“自动修复”

你现在 DockerBuildAgent 有一个行为：

```text
requirements.txt pip install 失败后自动放宽版本约束重试
```

这个能力很诱人，但要小心。它可能导致：

```text
原本 repo 明确要求旧版本
你放宽后装了新版本
build 成功
但运行时行为不可信
```

建议把它改成显式策略：

```bash
--dependency-strategy strict
--dependency-strategy relax
--dependency-strategy none
```

## strict

默认模式。

```text
完全按 requirements.txt 安装
失败就报告失败
```

## relax

实验模式。

```text
版本冲突时尝试放宽
报告中必须标记：dependencies were modified
```

## none

只构建基础 Python 环境，不安装 repo 依赖。

适合只跑 `--help` 或 scan。

```text
Docker build 更容易成功，但 smoke run 可能 import error
```

报告中显示：

```text
Dependency strategy: relax
Modified requirements: yes
Original requirements saved at env/requirements.original.txt
Relaxed requirements saved at env/requirements.relaxed.txt
```

这会让结果更可信。

---

# 第六优先级：失败分类要更细

你现在 build failure 分类有：

```text
包找不到
依赖冲突
CUDA
网络
Python 版本不兼容
```

很好。下一步给 smoke run 也做分类。

## Smoke failure categories

建议加：

```text
import_error
missing_dependency
missing_dataset
missing_checkpoint
argument_error
cuda_error
file_not_found
permission_error
network_blocked
timeout
runtime_error
unknown
```

简单正则就够：

```python
def classify_smoke_failure(stderr: str, stdout: str) -> str:
    text = (stderr + "\n" + stdout).lower()

    if "modulenotfounderror" in text or "no module named" in text:
        return "missing_dependency"
    if "filenotfounderror" in text:
        return "file_not_found"
    if "cuda" in text or "nvidia" in text:
        return "cuda_error"
    if "checkpoint" in text or ".pth" in text or ".ckpt" in text:
        return "missing_checkpoint"
    if "dataset" in text or "data path" in text:
        return "missing_dataset"
    if "usage:" in text and "error:" in text:
        return "argument_error"
    if "timed out" in text:
        return "timeout"

    return "unknown"
```

然后报告里显示：

```text
Smoke failed because: missing_dependency

Detected evidence:
ModuleNotFoundError: No module named 'cv2'

Suggested next step:
Add opencv-python or system libgl dependencies.
```

这会极大提高报告价值。

---

# 第七优先级：加运行 Telemetry

你之前提到 API 调用次数。现在正适合把 telemetry 加进去。

## TaskState 增加

```python
class ApiCallRecord(BaseModel):
    provider: str
    endpoint: str
    purpose: str
    success: bool
    status_code: int | None = None
    duration_ms: int | None = None


class StepTiming(BaseModel):
    step: str
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    success: bool
```

`TaskState`：

```python
api_calls: list[ApiCallRecord] = Field(default_factory=list)
step_timings: list[StepTiming] = Field(default_factory=list)
```

报告里显示：

```text
Execution telemetry:
- PaperIngestAgent: 12.4s
- PaperUnderstandingAgent: 3.1s
- GitHubSearchAgent: 8.8s
- RepoEvaluationAgent: 2.0s
- DockerBuildAgent: 184.2s
- SmokeRunAgent: 4.3s
- ReportWriterAgent: 2.5s

API calls:
- arXiv: 2
- GitHub: 9
- LLM: 2
```

这样你马上知道瓶颈在哪。

---

# 第八优先级：LLM 使用要可控

你现在多个地方 LLM 优先：

```text
paper understanding
smoke command selection
report conclusion
```

建议加全局开关：

```bash
--llm off
--llm auto
--llm required
```

## llm=off

完全规则模式。

用于 benchmark baseline。

## llm=auto

默认模式。

LLM 可用就用，失败就降级。

## llm=required

研究/调试模式。

LLM 失败则本次任务失败。

## 加调用预算

```bash
--max-llm-calls 3
```

在 TaskState 里记录：

```text
llm_calls_used
llm_calls_limit
```

否则后面 repair loop 一加，调用次数可能失控。

---

# 第九优先级：安全审计

你现在 command safety 做得不错：

```text
只允许 python / pytest
禁止 shell 元字符
只允许 --help/-h
Docker network none
只读挂载
resource limits
```

下一步重点是 Docker build 阶段。

## Docker build 风险

`pip install -r requirements.txt` 和 `pip install -e .` 都可能执行任意代码。

所以报告里应该明确写：

```text
Security note:
Docker build executes package installation scripts from the repository.
Do not run docker backend on untrusted malicious repositories.
```

## 增加安全模式

```bash
--safe-mode strict
--safe-mode normal
```

### strict

```text
不 pip install -e .
不运行 setup.py
不安装 requirements
只做 static scan
```

### normal

```text
安装 requirements
可选 pip install -e .
```

### unsafe / experimental

```text
允许更复杂 repair
允许 README command parsing
```

默认建议：

```text
safe-mode normal
```

但不要默认做 repair。

---

# 第十优先级：支持 Papers with Code / project page

GitHub discovery 现在只搜 GitHub 和论文文本。之后可以加：

```text
Papers with Code lookup
arXiv abstract page comments
paper official project page
README badges / links
```

但这不是现在最优先。

建议排在 gold set 和 telemetry 之后。

---

# 第十一优先级：缓存

当前重复跑同一篇论文可能会重复下载 PDF、重复 GitHub API、重复 clone、重复 build。

加缓存会大幅改善体验。

## 缓存对象

```text
arxiv metadata
arxiv pdf
github repo info
github readme
cloned repo zip
docker build result
```

## 简单实现

```text
.cache/
├── arxiv/
│   ├── 1911.11763.json
│   └── 1911.11763.pdf
├── github/
│   └── magicleap__SuperGluePretrainedNetwork.readme.txt
└── repos/
    └── magicleap__SuperGluePretrainedNetwork/
```

CLI：

```bash
--use-cache
--no-cache
--refresh-cache
```

默认建议：

```text
use-cache = true
```

---

# 推荐迭代路线

## v0.1.1：稳定性版本

目标：让现有功能更可调试。

做这些：

```text
1. backend=none/local/docker
2. gold_set runner
3. API calls + step timing telemetry
4. repo candidates top 5 in report
5. smoke failure classification
6. report 中展示 command candidate selection reason
```

验收：

```bash
paper-smoke eval-goldset --gold-set examples/gold_set.json --backend none
```

必须输出 summary。

---

## v0.1.2：可靠 Docker 版本

目标：让 Docker 失败更可解释。

做这些：

```text
1. dependency-strategy strict/relax/none
2. Docker build logs structured summary
3. safe-mode strict/normal
4. Docker build security note
5. Docker image cleanup command
```

新增命令：

```bash
paper-smoke clean --older-than 7d
```

验收：

```bash
paper-smoke run \
  --input https://arxiv.org/abs/1911.11763 \
  --repo-dir ./SuperGluePretrainedNetwork \
  --backend docker \
  --dependency-strategy strict
```

---

## v0.1.3：Repo discovery 提升版

目标：提高自动找 repo 的准确率。

做这些：

```text
1. candidate evidence model
2. README title / arXiv ID / method match scoring
3. fork / archived / pushed_at 降权
4. Papers with Code optional lookup
5. manual repo correction flow
```

新增命令：

```bash
paper-smoke search-repo --input https://arxiv.org/abs/1911.11763
```

只输出候选 repo，不跑后续 pipeline。

---

## v0.2.0：Controlled Repair

目标：有限、可解释的自动修复。

只做非常保守的 repair：

```text
1. missing_dependency → classify and suggest, not auto install by default
2. cuda_error → retry with CUDA_VISIBLE_DEVICES=""
3. argument_error → try --help instead of bare command
4. requirements conflict → optional relax strategy
```

每次 repair 必须记录：

```json
{
  "attempt": 1,
  "reason": "cuda_error",
  "change": "set CUDA_VISIBLE_DEVICES=''",
  "result": "failed"
}
```

不要做无限循环。

---

# 当前架构中我会马上调整的点

## 1. LLM 不应该“优先”用于 smoke command

Smoke command 选择最好先规则，LLM 只用于补充。

原因是 README 里很多命令会包含：

```bash
wget ...
pip install ...
python train.py ...
bash scripts/download.sh
```

LLM 可能会被 README 诱导推荐不适合 smoke 的命令。

推荐顺序：

```text
1. 规则生成安全候选命令
2. LLM 只对候选命令排序或解释
3. 最终仍走 command_safety
```

不要让 LLM 从 README 自由生成命令。

---

## 2. Docker requirements 放宽要标记为 experimental

自动放宽版本约束可能让 build 成功但结果不可信。

建议默认：

```text
dependency-strategy = strict
```

用户显式指定才 relax：

```bash
--dependency-strategy relax
```

报告必须说明：

```text
Dependencies were modified from the repository specification.
This result is not a faithful environment reproduction.
```

---

## 3. 报告应该区分“工具失败”和“repo 不可复现”

这很重要。

比如：

```text
GitHub API 429
Docker daemon not running
arXiv download failed
LLM JSON parse failed
```

这些是工具/环境失败，不代表论文 repo 不可复现。

而：

```text
requirements conflict
missing checkpoint
no runnable script
requires unavailable dataset
```

才是 repo reproduction 风险。

建议 final status 拆成两层：

```python
pipeline_status: success | failed
reproduction_status: success | partial | blocked | unknown
failure_owner: tool | repo | environment | user_input | network
```

报告会更专业。

---

# 建议下一步实际执行顺序

我会按这个顺序来：

```text
1. 加 backend=none/local/docker
2. 加 gold_set runner
3. 加 telemetry
4. 报告展示 top repo candidates 和 API usage
5. 拆 command selection artifact
6. 加 smoke failure classification
7. Docker dependency-strategy 改成 strict/relax/none
8. 再考虑 repair loop
```

这 8 步完成后，你的项目就会从“能跑一次”变成“能系统评估和持续改进”。

---

# 一个很实用的 v0.1.1 目标

你可以把下一版目标定成：

```text
paper-smoke v0.1.1:
A measurable smoke reproduction evaluator.
```

验收标准：

```bash
paper-smoke eval-goldset \
  --gold-set examples/gold_set.json \
  --backend none
```

输出：

```text
10 papers tested
10 reports generated
7 correct repos found
8 smoke commands selected
0 code executed
```

然后再跑：

```bash
paper-smoke eval-goldset \
  --gold-set examples/gold_set.json \
  --backend docker
```

输出：

```text
10 papers tested
4 Docker builds succeeded
3 smoke commands succeeded
6 failures classified
10 reports generated
```

到这个阶段，你就能非常清楚地知道 agent 下一步该优化哪里，而不是凭感觉改。

---

# 结论

你的当前实现已经完成了主链路。下一步不要急着加更复杂的 agent，而是升级成一个**可评估、可诊断、可控的 smoke reproduction system**。

优先级最高的是：

```text
gold set eval
backend none/local/docker
telemetry
failure classification
repo candidate evidence
controlled dependency strategy
```

等这些基础设施稳定后，再加自动 repair、多轮 agent、Papers with Code、LLM 深度理解，才不会把系统变成一个难以调试的黑箱。
