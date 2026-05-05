from app.agents.input_resolver_agent import InputResolverAgent


def test_resolver_validates_existing_local_pdf(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    result = InputResolverAgent().resolve(f"@{pdf}")

    assert result.success is True
    assert result.input_kind == "local_pdf"
    assert result.input_value == str(pdf)
    assert result.searched is False


def test_resolver_fails_missing_pdf():
    result = InputResolverAgent().resolve("/missing/paper.pdf")

    assert result.success is False
    assert "不存在" in result.failure_reason
    assert "不会自行搜索 arXiv" in result.failure_reason


def test_resolver_rejects_arxiv_url_without_searching():
    result = InputResolverAgent().resolve("https://arxiv.org/abs/2306.14289")

    assert result.success is False
    assert result.input_kind == "local_pdf"
    assert result.searched is False
    assert "不会自行搜索 arXiv" in result.failure_reason


def test_resolver_rejects_plain_title_without_searching():
    result = InputResolverAgent().resolve("复现 Useful Paper")

    assert result.success is False
    assert result.input_kind == "local_pdf"
    assert result.searched is False
    assert "不会自行搜索 arXiv" in result.failure_reason


def test_resolver_rejects_directory(tmp_path):
    result = InputResolverAgent().resolve(str(tmp_path))

    assert result.success is False
    assert "不是 PDF 文件" in result.failure_reason
