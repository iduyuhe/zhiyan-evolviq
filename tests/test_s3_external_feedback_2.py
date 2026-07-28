"""S3 外部反馈第二批（#45）回归锁：DeepSeek 模型名迁移 + V4 思考模式。

背景（GitHub @xingswxingsw #45）：DeepSeek 于 2026-07-24 正式弃用
deepseek-reasoner / deepseek-chat，统一迁移到 V4 系列；deepseek-v4-flash
同时支持思考/非思考模式，推理模型须显式开启 thinking，否则退化为
非思考模式、丧失推理能力。
"""
import asyncio
from unittest.mock import patch

from src.common.config import settings
from src.common.llm_client import LLMClient


def test_config_uses_deepseek_v4_models():
    # #45：弃用的 deepseek-reasoner / deepseek-chat 不得再作为默认值
    assert settings.llm_reasoning_model == "deepseek-v4-flash"
    assert settings.llm_fast_model == "deepseek-v4-flash"
    assert "deepseek-reasoner" != settings.llm_reasoning_model
    assert "deepseek-chat" != settings.llm_fast_model


def _fake_client_capturing(captured: dict):
    """返回一个替身 httpx.AsyncClient，记录请求体 JSON 并返回最小响应。"""
    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    return _FakeClient


def _client_with_deepseek():
    """构造一个仅含 deepseek provider 的 LLMClient（不依赖真实 key）。"""
    client = LLMClient()
    client._providers["deepseek"] = {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "test-key",
        "fast_model": "deepseek-v4-flash",
        "reasoning_model": "deepseek-v4-flash",
    }
    client._default = "deepseek"
    return client


def test_reasoning_enables_thinking_for_v4():
    # #45：推理调用须开启 thinking 模式
    captured: dict = {}
    with patch("src.common.llm_client.httpx.AsyncClient", _fake_client_capturing(captured)):
        client = _client_with_deepseek()
        result = asyncio.run(client.chat([{"role": "user", "content": "hi"}], reasoning=True))
    assert result == "ok"
    assert captured["json"]["thinking"] == {"type": "enabled"}
    assert captured["json"]["reasoning_effort"] == "high"


def test_fast_model_no_thinking():
    # #45：快速（非推理）调用不得加 thinking，保持非思考模式
    captured: dict = {}
    with patch("src.common.llm_client.httpx.AsyncClient", _fake_client_capturing(captured)):
        client = _client_with_deepseek()
        asyncio.run(client.chat([{"role": "user", "content": "hi"}], reasoning=False))
    assert "thinking" not in captured["json"]
    assert "reasoning_effort" not in captured["json"]
