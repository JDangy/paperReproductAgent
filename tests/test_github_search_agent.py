from app.agents import github_search_agent
from app.agents.github_search_agent import GitHubSearchAgent
from app.core.state import PaperMetadata, ReproductionBrief, TaskState
from app.tools.github_tool import normalize_github_repo_url, normalize_project_page_url


def _state() -> TaskState:
    return TaskState(
        task_id="task_test",
        input_value="https://arxiv.org/abs/2302.05543",
        workspace_dir="workspace",
        task_dir="workspace/tasks/task_test",
        paper_metadata=PaperMetadata(
            title="Adding Conditional Control to Text-to-Image Diffusion Models",
            arxiv_id="2302.05543",
        ),
        reproduction_brief=ReproductionBrief(
            task="text-to-image generation with spatial conditioning",
            method_keywords=["ControlNet", "Stable Diffusion"],
            github_links_in_paper=[],
        ),
    )


def _repo(owner, name, stars, description="", fork=False):
    return {
        "html_url": f"https://github.com/{owner}/{name}",
        "owner": {"login": owner},
        "name": name,
        "stargazers_count": stars,
        "archived": False,
        "fork": fork,
        "description": description,
    }


def test_llm_reranks_existing_candidate_only(monkeypatch):
    def fake_search(query, max_results=5):
        if query == "Adding Conditional Control to Text-to-Image Diffusion Models":
            return [
                _repo("faverogian", "controlNet", 18),
            ]
        if query == "ControlNet":
            return [
                _repo("lllyasviel", "ControlNet", 33848, "Official ControlNet implementation"),
            ]
        return []

    monkeypatch.setattr(github_search_agent, "search_github_repos", fake_search)
    monkeypatch.setattr(github_search_agent, "get_repo_info", lambda owner, name: {
        "description": "Official ControlNet implementation" if owner == "lllyasviel" else "",
        "homepage": "",
        "fork": False,
        "archived": False,
        "stargazers_count": 33848 if owner == "lllyasviel" else 18,
    })
    monkeypatch.setattr(github_search_agent, "get_repo_readme", lambda owner, name: "")
    monkeypatch.setattr(github_search_agent, "call_llm_json", lambda **kwargs: {
        "selected_url": "https://github.com/lllyasviel/ControlNet",
        "confidence": 0.92,
        "reason": "The high-star repo with the method name is the official implementation.",
    })

    state = GitHubSearchAgent().run(_state())

    assert state.selected_repo.url == "https://github.com/lllyasviel/ControlNet"
    assert any("LLM rerank selected" in r for r in state.selected_repo.reasons)


def test_project_page_link_is_resolved_before_search(monkeypatch):
    state = _state()
    state.reproduction_brief.github_links_in_paper = ["https://co-tracker.github.io/"]

    monkeypatch.setattr(
        github_search_agent,
        "get_github_repo_urls_from_page",
        lambda url, max_results=5: ["https://github.com/facebookresearch/co-tracker"],
    )
    monkeypatch.setattr(github_search_agent, "get_repo_info", lambda owner, name: {
        "stargazers_count": 2000,
        "archived": False,
        "fork": False,
        "description": "Official CoTracker implementation",
    })
    monkeypatch.setattr(github_search_agent, "get_repo_readme", lambda owner, name: "")
    monkeypatch.setattr(github_search_agent, "search_github_repos", lambda query, max_results=5: [])
    monkeypatch.setattr(github_search_agent, "call_llm_json", lambda **kwargs: None)

    result = GitHubSearchAgent().run(state)

    assert result.selected_repo.url == "https://github.com/facebookresearch/co-tracker"
    assert result.selected_repo.source == "paper"


def test_bare_project_page_link_is_resolved_before_search(monkeypatch):
    state = _state()
    state.reproduction_brief.github_links_in_paper = ["www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24"]

    seen_urls = []

    def fake_resolve(url, max_results=5):
        seen_urls.append(url)
        return ["https://github.com/verlab/accelerated_features"]

    monkeypatch.setattr(github_search_agent, "get_github_repo_urls_from_page", fake_resolve)
    monkeypatch.setattr(github_search_agent, "get_repo_info", lambda owner, name: {
        "stargazers_count": 500,
        "archived": False,
        "fork": False,
        "description": "Official XFeat implementation",
    })
    monkeypatch.setattr(github_search_agent, "get_repo_readme", lambda owner, name: "")
    monkeypatch.setattr(github_search_agent, "search_github_repos", lambda query, max_results=5: [
        _repo("zju3dv", "EfficientLoFTR", 999)
    ])
    monkeypatch.setattr(github_search_agent, "call_llm_json", lambda **kwargs: None)

    result = GitHubSearchAgent().run(state)

    assert seen_urls == ["www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24"]
    assert result.selected_repo.url == "https://github.com/verlab/accelerated_features"
    assert result.selected_repo.source == "paper"


def test_normalize_project_page_url_adds_https_to_bare_domains():
    assert (
        normalize_project_page_url("www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24")
        == "https://www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24"
    )
    assert normalize_project_page_url("https://example.com/project") == "https://example.com/project"
    assert normalize_project_page_url("//example.com/project") == "https://example.com/project"
    assert (
        normalize_project_page_url("www.verlab.dcc.ufmg. br/descriptors/xfeat_cvpr24")
        == "https://www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24"
    )


def test_normalize_github_repo_url_drops_pdf_section_suffix():
    assert (
        normalize_github_repo_url("https://github.com/openai/whisper.2.Approach")
        == "https://github.com/openai/whisper"
    )


def test_keyword_ranking_prefers_method_names_over_generic_acronyms():
    ranked = GitHubSearchAgent()._rank_keywords_for_search([
        "Segment Anything Model",
        "MobileSAM",
        "ViT-H",
        "ViT-L",
        "ViT-B",
        "mask decoder",
    ])

    assert ranked[:2] == ["MobileSAM", "mask decoder"]
    assert ranked[-3:] == ["ViT-B", "ViT-H", "ViT-L"]
