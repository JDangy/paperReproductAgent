# TUI Frontend Handoff

本文档面向前端/TUI 实现方，说明 Paper Reproduction Agent 的后端能力、实时进度事件契约、推荐界面结构和会话回放方式。

## 目标

TUI 需要做成类似 Codex/Claude Code 的实时工作台：

1. 用户输入论文 PDF 路径、可选 repo/repo-dir 和 backend。
2. 后端开始运行复现流水线。
3. 前端实时显示每个阶段正在做什么，例如校验 PDF、调用 LLM、搜索 GitHub、clone repo、扫描脚本、构建 conda、运行 smoke、写报告。
4. 长任务完成后显示最终状态、报告路径和报告预览。
5. 支持查看日志、取消任务、恢复历史 session。

## 后端入口

CLI/TUI 入口在 `app/cli.py`：

```bash
/home/duyuan/miniconda3/envs/torch_py39_env/bin/python -m app.cli tui --backend conda
```

主要参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--workspace` | `settings.default_workspace` | 任务输出目录 |
| `--backend` | `conda` | `none`, `local`, `venv`, `conda`, `docker` |
| `--timeout-minutes` | 配置默认值 | 单步超时 |
| `--max-repair-attempts` | 配置默认值 | smoke 缺依赖自动修复次数 |

后端主流程函数是 `_run_pipeline(...)`。如果前端不复用现有 Textual App，而是自己做一层 UI，可以直接把这个函数放到后台线程/任务里跑，并通过 `progress_events(...)` 接收实时事件。

## Pipeline 阶段

当前主链路：

| Stage | 说明 | 常见实时动作 |
|---|---|---|
| `Pipeline` | 创建任务、取消等全局状态 | created task, cancelled |
| `Ingest paper` | 本地 PDF 解析 | validating PDF input, copying PDF, extracting PDF text, metadata extracted |
| `Understand paper` | 论文理解 | loading parsed text, asking LLM, LLM brief extracted, extracting benchmark protocol |
| `Search GitHub` | 仓库发现 | checking links, searching GitHub, scoring, reranking, selected repository |
| `Evaluate repo` | 仓库下载和静态评估 | cloning/copying repo, scanning structure, detecting risk flags, analyzing benchmark surface |
| `Build conda env` | conda 环境构建 | create env, install requirements, retry relaxed requirements, environment ready |
| `Build virtualenv` | venv 环境构建 | preparing environment, bootstrap/install steps, environment ready |
| `Build Docker image` | Docker 构建 | Dockerfile/build 相关动作 |
| `Run smoke command` | 保守 smoke 测试 | selected command, attempt N, missing dependency, repair dependency, attempt passed/failed |
| `Run benchmark reproduction` | 协议化 benchmark 尝试 | planning candidates, reviewing plan, running command, parsing outputs, fallback |
| `Run simple reproduction` | 轻量复现尝试 | selected command, completed/failed |
| `Write report` | 报告生成 | determined final status, generating insights, rendering template, wrote report |

## 实时事件模型

底层事件类是 `ProgressEvent`：

```python
@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    message: str
    level: str = "info"
    phase: str = "progress"
    detail: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
```

字段语义：

| 字段 | 类型 | 说明 |
|---|---|---|
| `stage` | string | 所属阶段，例如 `Search GitHub` |
| `message` | string | 当前动作短文本，例如 `searching GitHub` |
| `level` | string | `info`, `success`, `warning`, `error` |
| `phase` | string | `start`, `progress`, `finish`, `fail` |
| `detail` | string/null | 命令、路径、分数、失败原因等辅助信息 |
| `data` | object | 结构化附加数据，例如 `duration_ms`, `candidate_count`, `selected_repo` |

前端建议优先用 `phase` 判断卡片状态，用 `level` 决定颜色。

## AgentEvent 持久化契约

运行时桥接函数会把 `ProgressEvent` 转成 `AgentEvent`：

| `ProgressEvent.phase/level` | `AgentEvent.type` |
|---|---|
| `phase == "start"` | `tool_started` |
| `phase == "finish"` | `tool_finished` |
| `phase == "fail"` 或 `level == "error"` | `tool_failed` |
| 其他 | `tool_progress` |

`AgentEvent.payload` 结构：

```json
{
  "stage": "Search GitHub",
  "message": "selected repository",
  "level": "info",
  "phase": "progress",
  "detail": "https://github.com/example/repo (score=92.0)",
  "data": {
    "selected_repo": "https://github.com/example/repo",
    "candidate_count": 12
  }
}
```

事件会追加保存到：

```text
.paper-agent/sessions/<session_id>.jsonl
```

session 快照保存到：

```text
.paper-agent/sessions/<session_id>.state.json
```

前端做历史回放时读取 JSONL，按时间顺序 replay：

| Event type | 前端行为 |
|---|---|
| `user_message` | 显示用户气泡 |
| `assistant_message` | 显示助手文本 |
| `error` | 显示错误文本 |
| `tool_started` | 新建或激活阶段卡片 |
| `tool_progress` | 更新阶段卡片 body/detail |
| `tool_finished` | 标记卡片成功，展示耗时 |
| `tool_failed` | 标记卡片失败，展示错误原因 |

## 推荐 TUI 布局

建议首屏就是可操作工作台，不做 landing page。

```text
┌──────────────────────────────────────────────────────────────┐
│ Paper Reproduction Agent       session-ab12  ACT  conda       │
├──────────────────────────────────────────────────────────────┤
│ User: /home/user/paper.pdf                                    │
│ Assistant: 开始复现流水线。                                    │
│                                                              │
│ ▸ Ingest paper        running                                 │
│   extracting PDF text                                         │
│                                                              │
│ ✓ Understand paper    success  4.8s                           │
│   datasets=2, metrics=3, links=1                              │
│                                                              │
│ ▸ Search GitHub       running                                 │
│   searching GitHub: paper title github                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ ACT  backend=conda  status=running  paper=paper.pdf           │
├──────────────────────────────────────────────────────────────┤
│ > /run                                                        │
└──────────────────────────────────────────────────────────────┘
```

视觉建议：

| 状态 | Icon | 颜色建议 |
|---|---|---|
| running | `▸` 或 spinner | cyan/blue |
| success | `✓` | green |
| warning/progress warning | `!` | yellow |
| failed | `✗` | red |

每个 tool card 建议展示：

1. stage 名称。
2. 当前 status。
3. 最新 message/detail。
4. finish/fail 时展示 `data.duration_ms` 转换后的耗时。
5. 可折叠展开最近 N 条 progress 记录。

## 前端渲染状态机

推荐维护两个结构：

```ts
type ToolCardState = {
  stage: string
  status: "running" | "success" | "failed"
  message: string
  detail?: string
  durationMs?: number
  history: Array<{
    message: string
    level: string
    detail?: string
    data?: Record<string, unknown>
    timestamp: number
  }>
}

type SessionViewState = {
  messages: ChatMessage[]
  activeCardsByStage: Record<string, ToolCardState>
  completedCards: ToolCardState[]
}
```

处理规则：

```ts
function applyAgentEvent(event: AgentEvent) {
  if (event.type === "user_message") appendUser(event.payload.text)
  if (event.type === "assistant_message") appendAssistant(event.payload.text)
  if (event.type === "error") appendError(event.payload.text)

  if (event.type === "tool_started") {
    createCard(event.payload.stage, event.payload.message)
  }

  if (event.type === "tool_progress") {
    updateCard(event.payload.stage, {
      status: "running",
      message: event.payload.message,
      detail: event.payload.detail ?? event.payload.message,
      historyAppend: event.payload
    })
  }

  if (event.type === "tool_finished") {
    finishCard(event.payload.stage, {
      status: "success",
      detail: event.payload.detail,
      durationMs: event.payload.data?.duration_ms
    })
  }

  if (event.type === "tool_failed") {
    finishCard(event.payload.stage, {
      status: "failed",
      detail: event.payload.detail,
      durationMs: event.payload.data?.duration_ms
    })
  }
}
```

注意：同一个 stage 可能在同一次任务里只出现一次，也可能未来出现多次。前端不要只用 stage 做永久唯一 key；建议使用 `stage + sequence` 或事件顺序生成 card id。当前 Textual 版本也是这样处理的。

## 用户命令

当前 TUI 支持的 slash commands：

| 命令 | 说明 |
|---|---|
| `/help` | 显示帮助 |
| `/clear` | 清屏 |
| `/status` | 查看当前 task status/final status |
| `/plan` | 切换到只规划不执行 |
| `/act` | 切换到执行模式 |
| `/input <path>` | 设置论文 PDF |
| `/repo <url>` | 手动指定 GitHub repo |
| `/repo-dir <path>` | 使用本地 repo |
| `/backend conda|venv|docker|local|none` | 设置执行 backend |
| `/workspace <path>` | 设置输出目录 |
| `/timeout <minutes>` | 设置单步超时 |
| `/repairs <count>` | 设置 smoke 自动修复次数 |
| `/run` | 开始流水线 |
| `/report` | 查看报告 |
| `/logs env|conda|venv|build|smoke|stderr|stdout` | 查看日志 |
| `/cancel` | 请求取消 |
| `/sessions` | 列出历史 session |
| `/resume <id>` | 恢复历史 session |
| `/quit` 或 `/exit` | 退出 |
| `!<shell command>` | shell 命令，必须二次确认 |

## 任务输出目录

每次运行会创建 task 目录：

```text
<workspace>/tasks/<task_id>/
```

常用文件：

| 路径 | 说明 |
|---|---|
| `state.json` | 完整 TaskState |
| `paper/parsed_text.txt` | PDF 解析文本 |
| `paper/paper_metadata.json` | 基础元信息 |
| `paper/reproduction_brief.json` | 复现摘要 |
| `paper/benchmark_protocol_brief.json` | benchmark 协议摘要 |
| `evaluation/repo_score.json` | 仓库结构和可运行性评分 |
| `env/conda_build.log` | conda 构建日志 |
| `env/venv_build.log` | venv 构建日志 |
| `runs/smoke_001/run_summary.json` | smoke 摘要 |
| `runs/smoke_001/stdout.log` | smoke stdout |
| `runs/smoke_001/stderr.log` | smoke stderr |
| `runs/benchmark_001/benchmark_summary.json` | benchmark 摘要 |
| `runs/reproduction_001/reproduction_summary.json` | simple reproduction 摘要 |
| `report/reproduction_smoke_report.md` | Markdown 报告 |
| `report/reproduction_smoke_report.json` | 报告元数据 |

## 最终状态

报告中的 `final_status` 是最重要的最终结果：

| 状态 | 含义 |
|---|---|
| `benchmark_success` | 协议化 benchmark 运行成功 |
| `reproduction_success` | 轻量端到端复现运行成功 |
| `success` | 非 help smoke/demo/pytest 成功 |
| `partial_success_help_only` | 只有 `--help` 成功，不算完整复现 |
| `repo_found_but_env_failed` | repo 找到，但环境失败 |
| `repo_found_but_smoke_failed` | 环境可用，但 smoke 失败 |
| `repo_found_but_reproduction_failed` | 轻量复现失败 |
| `repo_found_but_benchmark_failed` | benchmark 失败 |
| `repo_found_reproduction_not_run` | 没有安全轻量复现命令 |
| `repo_found_benchmark_not_run` | 没有可运行 benchmark plan |
| `repo_found_smoke_not_run` | backend=none，只做静态评估 |
| `repo_not_found` | 没找到仓库 |
| `paper_parse_failed` | PDF 解析失败 |
| `failed` | 未得到结论性结果前异常失败 |

## 取消语义

`/cancel` 会设置 `session.cancel_requested = True`。后端会在阶段之间检查 `should_cancel()`，不会强杀正在运行的 subprocess。

前端文案建议：

```text
已发送取消请求，当前步骤结束后停止。
```

如果需要立即终止子进程，后端还需要进一步把 subprocess runner 改成可中断的 `Popen` 管理模式。

## 当前已知限制

1. 大部分 subprocess 仍使用 `subprocess.run(capture_output=True)`，所以命令 stdout/stderr 不是逐行流式输出，而是在命令结束后写入日志文件。
2. 进度已经能具体到 agent 内部动作，但还不是每个 pip/conda 下载包的逐行日志。
3. session JSONL 默认存到当前工作目录下 `.paper-agent/sessions/`，前端如果改变启动目录，需要统一 cwd 或显式传入 session base dir。
4. backend=`local` 会执行本机 repo 代码，前端需要明确提示风险。
5. `backend=none` 不执行代码，只适合静态评估和 repo discovery。

## 后续增强建议

前端优先级：

1. 做好 `AgentEvent` 的实时渲染和回放。
2. Tool card 支持折叠历史 progress。
3. 报告完成后展示 final status、short conclusion、报告路径和关键 next steps。
4. `/logs` 做成快捷面板，而不是只输出文本。
5. 对 `backend=local/docker/conda` 做明显风险和耗时提示。

后端优先级：

1. 把长命令执行从 `subprocess.run` 改成 `Popen`，逐行 emit `tool_progress`。
2. 为 `AgentEvent` 增加稳定的 `task_id`, `session_id`, `event_id`, `card_id`。
3. 增加 WebSocket/SSE 适配层，方便非 Textual 前端消费。
4. 增加机器可读的 `/status` JSON 输出或本地 IPC 接口。
