"""Provider-neutral configuration and packaged-default tests."""

from bench_cleanser.pipeline import load_config


def test_packaged_default_uses_openai_compatible_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gateway.example/v1")

    config = load_config(None)

    assert config.llm_provider == "openai-compatible"
    assert config.llm_api_key == "test-key"
    assert config.llm_base_url == "https://gateway.example/v1"
    assert config.llm_request_timeout_seconds > 0
    assert config.llm_retry_timeout_seconds >= config.llm_request_timeout_seconds


def test_explicit_config_loads_deadlines_and_visitation_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOM_LLM_KEY", "secret")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
llm:
  provider: local
  api_key_env: CUSTOM_LLM_KEY
  base_url_env: UNUSED_BASE_URL
  base_url: http://localhost:8000/v1
  model: local-model
  request_timeout_seconds: 12
  retry_timeout_seconds: 34
code_visitation:
  enabled: false
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm_provider == "local"
    assert config.llm_api_key == "secret"
    assert config.llm_base_url == "http://localhost:8000/v1"
    assert config.llm_request_timeout_seconds == 12
    assert config.llm_retry_timeout_seconds == 34
    assert config.code_visitation_enabled is False
