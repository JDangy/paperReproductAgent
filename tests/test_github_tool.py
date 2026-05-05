from app.tools.github_tool import (
    extract_github_repo_urls_from_html,
    normalize_github_repo_url,
    parse_github_url,
)


def test_parse_github_url_normalizes_repo_suffix():
    assert parse_github_url("https://github.com/owner/repo.git") == ("owner", "repo")


def test_normalize_github_repo_url():
    assert (
        normalize_github_repo_url("https://github.com/Owner/Repo.git/")
        == "https://github.com/owner/repo"
    )


def test_extract_github_repo_urls_from_html_dedupes():
    html = """
    <a href="https://github.com/facebookresearch/co-tracker">code</a>
    <a href="https://github.com/facebookresearch/co-tracker/issues">issues</a>
    <a href="https://github.com/features/actions">not a repo</a>
    """

    assert extract_github_repo_urls_from_html(html) == [
        "https://github.com/facebookresearch/co-tracker"
    ]
