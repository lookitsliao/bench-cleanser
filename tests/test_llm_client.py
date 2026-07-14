"""Tests for LLM parsing, cache semantics, and hard request deadlines."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from bench_cleanser.llm_client import LLMClient


class TestExtractJson:
    """Test the static _extract_json method."""

    def test_clean_json(self):
        result = LLMClient._extract_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = LLMClient._extract_json(text)
        assert result == {"key": "value"}

    def test_fenced_no_lang_tag(self):
        text = 'Some text\n```\n{"a": 1}\n```\nMore text'
        result = LLMClient._extract_json(text)
        assert result == {"a": 1}

    def test_brace_fallback(self):
        text = 'Here is the result: {"verdict": "CLEAN"} done.'
        result = LLMClient._extract_json(text)
        assert result == {"verdict": "CLEAN"}

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            LLMClient._extract_json("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            LLMClient._extract_json("")

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}, "flag": true}'
        result = LLMClient._extract_json(text)
        assert result == {"outer": {"inner": [1, 2, 3]}, "flag": True}


class TestCacheKeyDeterminism:
    """Verify cache keys are deterministic for the same inputs."""

    def test_same_input_same_key(self):
        from bench_cleanser.cache import ResponseCache

        key1 = ResponseCache.make_key("sys", "user", "model-1")
        key2 = ResponseCache.make_key("sys", "user", "model-1")
        assert key1 == key2

    def test_different_input_different_key(self):
        from bench_cleanser.cache import ResponseCache

        key1 = ResponseCache.make_key("sys", "user_a", "model-1")
        key2 = ResponseCache.make_key("sys", "user_b", "model-1")
        assert key1 != key2

    def test_different_model_different_key(self):
        from bench_cleanser.cache import ResponseCache

        key1 = ResponseCache.make_key("sys", "user", "model-1")
        key2 = ResponseCache.make_key("sys", "user", "model-2")
        assert key1 != key2

    def test_key_is_hex_string(self):
        from bench_cleanser.cache import ResponseCache

        key = ResponseCache.make_key("a", "b", "c")
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in key)

    def test_tuple_boundaries_cannot_collide(self):
        from bench_cleanser.cache import ResponseCache

        assert ResponseCache.make_key("ab", "c", "") != ResponseCache.make_key(
            "a", "bc", ""
        )


class _SchemaA(BaseModel):
    value: str


class _SchemaB(BaseModel):
    value: str
    count: int


def _bare_client() -> LLMClient:
    client = object.__new__(LLMClient)
    client._provider = "test-provider"
    client._base_url = "https://example.test/v1"
    client._model = "model-X"
    client._max_tokens = 123
    client._reasoning_effort = None
    return client


class TestSemanticCacheKeys:
    def test_text_and_json_calls_do_not_collide(self):
        client = _bare_client()
        text_key = client._cache_key("sys", "user", response_mode="text")
        json_key = client._cache_key("sys", "user", response_mode="json_object")
        assert text_key != json_key

    def test_different_schemas_do_not_collide(self):
        client = _bare_client()
        key_a = client._structured_cache_key("sys", "user", _SchemaA)
        key_b = client._structured_cache_key("sys", "user", _SchemaB)
        assert key_a != key_b

    def test_endpoint_identity_is_part_of_key(self):
        first = _bare_client()
        second = _bare_client()
        second._base_url = "https://other.example/v1"
        assert first._cache_key("sys", "user", response_mode="text") != second._cache_key(
            "sys", "user", response_mode="text"
        )


@pytest.mark.asyncio
async def test_call_api_enforces_request_and_total_retry_deadlines():
    class HangingCompletions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            await asyncio.Event().wait()

    completions = HangingCompletions()
    client = _bare_client()
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    client._retry_attempts = 20
    client._retry_delay = 0.002
    client._request_timeout = 0.01
    client._retry_timeout = 0.04
    client._request_semaphore = asyncio.Semaphore(2)

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="retry deadline"):
        await client._call_api("sys", "user")
    elapsed = time.monotonic() - started

    assert completions.calls >= 1
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_call_api_enforces_max_concurrent_requests():
    class TrackingCompletions:
        def __init__(self):
            self.in_flight = 0
            self.peak = 0

        async def create(self, **kwargs):
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            try:
                await asyncio.sleep(0.01)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
                )
            finally:
                self.in_flight -= 1

    completions = TrackingCompletions()
    client = _bare_client()
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    client._retry_attempts = 1
    client._retry_delay = 0
    client._request_timeout = 1
    client._retry_timeout = 2
    client._request_semaphore = asyncio.Semaphore(3)

    results = await asyncio.gather(
        *(client._call_api("sys", f"user-{index}") for index in range(15))
    )

    assert results == ["ok"] * 15
    assert completions.peak == 3
