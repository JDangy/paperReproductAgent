import os

from app.tools.network import sanitize_proxy_env


def test_sanitize_proxy_env_removes_socks5h_all_proxy_when_http_proxy_exists(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:7890")

    sanitize_proxy_env()

    assert "ALL_PROXY" not in os.environ
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:7890"


def test_sanitize_proxy_env_converts_socks5h_protocol_proxy(monkeypatch):
    monkeypatch.delenv("ALL_PROXY", raising=False)
    monkeypatch.delenv("all_proxy", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "socks5h://127.0.0.1:7890")

    sanitize_proxy_env()

    assert os.environ["HTTPS_PROXY"] == "socks5://127.0.0.1:7890"
