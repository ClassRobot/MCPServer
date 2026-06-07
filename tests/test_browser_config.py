"""Tests for browser search settings loaded from YAML and environment variables."""

from __future__ import annotations

import pytest

from mcp_server.config import load_server_settings


def test_load_server_settings_reads_browser_search_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "browser_search.yaml").write_text(
        "\n".join(
            [
                "browser:",
                "  timeout_ms: 22000",
                "  max_results: 7",
                "cache:",
                "  ttl_sec: 900",
                "filter:",
                "  strict_natural_results_only: true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))

    settings = load_server_settings()

    assert settings.browser_search.browser.timeout_ms == 22000
    assert settings.browser_search.browser.max_results == 7
    assert settings.browser_search.cache.ttl_sec == 900
    assert settings.browser_search.filter.strict_natural_results_only is True


def test_environment_overrides_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "browser_search.yaml").write_text(
        "\n".join(
            [
                "browser:",
                "  headless: false",
                "cache:",
                "  enabled: false",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_BROWSER_HEADLESS", "true")
    monkeypatch.setenv("MCP_BROWSER_CACHE_ENABLED", "true")

    settings = load_server_settings()

    assert settings.browser_search.browser.headless is True
    assert settings.browser_search.cache.enabled is True


def test_invalid_browser_timeout_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "browser_search.yaml").write_text(
        "browser:\n  timeout_ms: -1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="MCP_BROWSER_TIMEOUT_MS must be a positive integer"):
        load_server_settings()


def test_load_server_settings_reads_markitdown_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    allowed_root = tmp_path / "documents"
    allowed_root.mkdir()
    (config_dir / "markitdown.yaml").write_text(
        "\n".join(
            [
                "enabled: true",
                "storage:",
                "  output_dir: runtime/md",
                "  save_output_by_default: false",
                "security:",
                "  allowed_roots:",
                "    - documents",
                "  max_input_bytes: 1024",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))

    settings = load_server_settings()

    assert settings.markitdown.enabled is True
    assert settings.markitdown.output_dir == (tmp_path / "runtime" / "md").resolve()
    assert settings.markitdown.save_output_by_default is False
    assert settings.markitdown.allowed_roots == (allowed_root.resolve(),)
    assert settings.markitdown.max_input_bytes == 1024


def test_environment_overrides_markitdown_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "markitdown.yaml").write_text("enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_MARKITDOWN_ENABLED", "true")
    monkeypatch.setenv("MCP_MARKITDOWN_OUTPUT_DIR", "runtime/from-env")

    settings = load_server_settings()

    assert settings.markitdown.enabled is True
    assert settings.markitdown.output_dir == (tmp_path / "runtime" / "from-env").resolve()
