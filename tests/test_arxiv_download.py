from __future__ import annotations

"""Tests for app/tools/arxiv_download.py"""

import pytest
from app.tools.arxiv_download import (
    normalize_arxiv_id, arxiv_pdf_url, arxiv_abs_url,
    safe_arxiv_pdf_filename, make_progress_bar, download_arxiv_pdf,
)


def test_normalize_plain_id():
    assert normalize_arxiv_id("1911.11763") == "1911.11763"


def test_normalize_with_prefix():
    assert normalize_arxiv_id("arXiv:1911.11763") == "1911.11763"


def test_normalize_abs_url():
    assert normalize_arxiv_id("https://arxiv.org/abs/1911.11763") == "1911.11763"


def test_normalize_pdf_url():
    assert normalize_arxiv_id("https://arxiv.org/pdf/1911.11763.pdf") == "1911.11763"


def test_normalize_pdf_url_no_ext():
    assert normalize_arxiv_id("https://arxiv.org/pdf/1911.11763") == "1911.11763"


def test_normalize_version():
    assert normalize_arxiv_id("https://arxiv.org/abs/1911.11763v1") == "1911.11763v1"


def test_normalize_invalid():
    with pytest.raises(ValueError):
        normalize_arxiv_id("not-an-id")


def test_normalize_empty():
    with pytest.raises(ValueError):
        normalize_arxiv_id("")


def test_arxiv_pdf_url():
    assert arxiv_pdf_url("1911.11763") == "https://arxiv.org/pdf/1911.11763.pdf"


def test_arxiv_abs_url():
    assert arxiv_abs_url("1911.11763") == "https://arxiv.org/abs/1911.11763"


def test_safe_filename():
    assert safe_arxiv_pdf_filename("1911.11763") == "arXiv-1911.11763.pdf"


def test_safe_filename_version():
    assert safe_arxiv_pdf_filename("1911.11763v1") == "arXiv-1911.11763v1.pdf"


def test_make_progress_bar():
    bar = make_progress_bar(50, width=10)
    assert "50%" in bar
    assert "█" in bar


def test_make_progress_bar_none():
    assert make_progress_bar(None) == ""


def test_project_pdf_dir():
    from app.core.paths import find_project_root, project_pdf_dir
    assert project_pdf_dir() == find_project_root() / "pdf"


def test_arxiv_commands_registered():
    from app.tui.commands import COMMANDS
    assert "arxiv" in COMMANDS
    assert "download-arxiv" in COMMANDS


def test_download_arxiv_pdf_mock(tmp_path, monkeypatch):
    """Mock httpx.stream to test download flow without network."""
    import httpx

    class MockStream:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-length": "2000"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield b"%PDF-" + b"x" * 2000

    def mock_stream(*a, **kw):
        return MockStream()

    monkeypatch.setattr(httpx, "stream", mock_stream)

    result = download_arxiv_pdf("1911.11763", output_dir=tmp_path)
    assert result.success
    assert result.pdf_path is not None
    assert result.pdf_path.exists()
    assert result.pdf_path.suffix == ".pdf"


def test_download_arxiv_pdf_reuses_existing(tmp_path):
    """If file already exists, should reuse without downloading."""
    pdf_path = tmp_path / "arXiv-1911.11763.pdf"
    pdf_path.write_bytes(b"%PDF-mock content")

    result = download_arxiv_pdf("1911.11763", output_dir=tmp_path)
    assert result.success
    assert result.reused_existing
    assert result.pdf_path == pdf_path
