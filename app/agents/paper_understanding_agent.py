from __future__ import annotations

import logging
from pathlib import Path

from app.core.file_utils import save_json
from app.core.state import TaskState, ReproductionBrief
from app.tools.llm import call_llm_json
from app.tools.paper_parser import (
    extract_datasets,
    extract_metrics,
    extract_tasks,
    extract_method_keywords,
)
from app.tools.pdf_tool import extract_github_links

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a research paper analysis assistant. Given the text of an academic paper, \
extract structured information for reproduction purposes.

Respond with a JSON object containing exactly these keys:
- "task": string or null — the main research task (e.g. "image classification", \
"object detection", "text generation")
- "datasets": list of strings — datasets mentioned (e.g. ["ImageNet", "COCO"])
- "metrics": list of strings — evaluation metrics (e.g. ["accuracy", "F1", "mAP"])
- "method_keywords": list of strings — key method/technique names mentioned \
frequently (max 10)
- "github_links": list of strings — any GitHub URLs found in the paper
- "confidence": float between 0.0 and 1.0 — your confidence in this extraction

Only include items you are confident about. Return empty lists if unsure."""


class PaperUnderstandingAgent:
    def run(self, state: TaskState) -> TaskState:
        task_dir = Path(state.task_dir)
        parsed_text_path = task_dir / "paper" / "parsed_text.txt"

        if not parsed_text_path.exists():
            state.errors.append({"agent": "PaperUnderstandingAgent", "error": "parsed_text.txt not found"})
            state.status = "failed"
            return state

        text = parsed_text_path.read_text(encoding="utf-8", errors="ignore")

        brief = self._llm_understand(text)
        if brief is None:
            logger.info("LLM unavailable or failed, falling back to heuristic parsing")
            brief = self._heuristic_understand(text)

        state.reproduction_brief = brief
        save_json(task_dir / "paper" / "reproduction_brief.json", brief)

        state.status = "paper_understood"
        return state

    def _llm_understand(self, text: str) -> ReproductionBrief | None:
        truncated = text[:6000]
        result = call_llm_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Analyze the following paper text and extract structured information:\n\n{truncated}",
            purpose="paper_understanding",
        )
        if result is None:
            return None

        try:
            return ReproductionBrief(
                task=result.get("task"),
                datasets=result.get("datasets", []),
                metrics=result.get("metrics", []),
                method_keywords=result.get("method_keywords", []),
                github_links_in_paper=result.get("github_links", []),
                confidence=result.get("confidence", 0.5),
            )
        except Exception as e:
            logger.warning("Failed to parse LLM result into ReproductionBrief: %s", e)
            return None

    def _heuristic_understand(self, text: str) -> ReproductionBrief:
        tasks = extract_tasks(text)
        return ReproductionBrief(
            task=tasks[0] if tasks else None,
            datasets=extract_datasets(text),
            metrics=extract_metrics(text),
            method_keywords=extract_method_keywords(text),
            github_links_in_paper=extract_github_links(text),
            confidence=0.5,
        )
