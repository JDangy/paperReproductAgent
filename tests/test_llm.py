from app.tools import llm


def test_call_llm_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", None)

    assert llm.call_llm("system", "user") is None


def test_call_llm_returns_none_when_openai_package_unavailable(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(llm, "OpenAI", None)

    assert llm.call_llm("system", "user") is None


def test_call_llm_returns_none_when_client_initialization_fails(monkeypatch):
    class BrokenOpenAI:
        def __init__(self, **kwargs):
            raise ValueError("Unknown scheme for proxy URL")

    monkeypatch.setattr(llm.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(llm, "OpenAI", BrokenOpenAI)

    assert llm.call_llm("system", "user") is None
