from app.agents import paper_ingest_agent
from app.agents.paper_ingest_agent import PaperIngestAgent
from app.core.state import TaskState


def _state(tmp_path, input_value):
    task_dir = tmp_path / "task"
    return TaskState(
        task_id="task",
        input_value=input_value,
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="none",
    )


def test_paper_ingest_reads_existing_local_pdf(tmp_path, monkeypatch):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4")
    state = _state(tmp_path, f"@{source_pdf}")

    monkeypatch.setattr(paper_ingest_agent, "extract_text_from_pdf", lambda path: "A Local Paper\nAbstract\nBody")
    monkeypatch.setattr(
        paper_ingest_agent,
        "extract_basic_metadata",
        lambda text: {"title": "A Local Paper", "abstract": "Body"},
    )

    result = PaperIngestAgent().run(state)

    assert result.status == "paper_ingested"
    assert result.paper_input.input_type == "pdf"
    assert result.paper_input.arxiv_id is None
    assert result.paper_metadata.title == "A Local Paper"
    assert (tmp_path / "task" / "input" / "paper.pdf").exists()


def test_paper_ingest_rejects_arxiv_url(tmp_path):
    state = _state(tmp_path, "https://arxiv.org/abs/2306.14289")

    result = PaperIngestAgent().run(state)

    assert result.status == "failed"
    assert result.paper_input.input_type == "unknown"
    assert "local PDF path" in result.errors[0]["error"]
