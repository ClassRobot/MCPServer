"""Configuration models and loaders for the MCP server scaffold."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

TransportName = Literal["stdio", "sse", "streamable-http"]
ProviderName = Literal["bing"]
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

DEFAULT_SERVER_NAME = "MCP Server"
DEFAULT_SERVER_INSTRUCTIONS = (
    "A starter MCP server scaffold. Extend this server with project-specific "
    "tools, resources, and prompts."
)
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BROWSER_CONFIG_PATH = DEFAULT_PROJECT_ROOT / "config" / "browser_search.yaml"
DEFAULT_LOGGING_CONFIG_PATH = DEFAULT_PROJECT_ROOT / "config" / "logging.yaml"

DEFAULT_RUNTIME_ROOT = DEFAULT_PROJECT_ROOT / "runtime"
DEFAULT_CACHE_BASE_DIR = DEFAULT_RUNTIME_ROOT / "cache" / "browser-search"
DEFAULT_RENDER_OUTPUT_DIR = DEFAULT_RUNTIME_ROOT / "render"
DEFAULT_LOG_PATH = DEFAULT_RUNTIME_ROOT / "logs" / "mcp-server.log"
DEFAULT_SESSIONS_DIR = DEFAULT_RUNTIME_ROOT / "sessions"


@dataclass(frozen=True, slots=True)
class BrowserSettings:
    """Browser runtime settings shared by low-level tools and high-level search."""

    headless: bool = True
    timeout_ms: int = 15_000
    session_ttl_sec: int = 600
    default_provider: ProviderName = "bing"
    max_results: int = 5
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class SearchCacheSettings:
    """Cache settings for structured browser search results."""

    enabled: bool = True
    ttl_sec: int = 1_800
    base_dir: Path = DEFAULT_CACHE_BASE_DIR
    max_entries: int = 256


@dataclass(frozen=True, slots=True)
class SearchFilterSettings:
    """Filtering settings for search results extracted from providers."""

    ads_enabled: bool = True
    strict_natural_results_only: bool = False


@dataclass(frozen=True, slots=True)
class BrowserSearchSettings:
    """Aggregate settings for browser-driven search features."""

    browser: BrowserSettings = field(default_factory=BrowserSettings)
    cache: SearchCacheSettings = field(default_factory=SearchCacheSettings)
    filter: SearchFilterSettings = field(default_factory=SearchFilterSettings)


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Settings for terminal and file-based structured logging."""

    level: str = "INFO"
    console_enabled: bool = True
    console_color_enabled: bool = True
    file_enabled: bool = True
    file_path: Path = DEFAULT_LOG_PATH
    retention_days: int = 14
    tool_args_enabled: bool = False
    max_field_length: int = 100


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Settings for the persistence layer (optional SQL history)."""

    enabled: bool = False
    sqlalchemy_url: str | None = None
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    def __post_init__(self) -> None:
        """Ensure the database URL uses an async driver if provided."""
        if self.sqlalchemy_url:
            normalized = _normalize_sqlalchemy_url(self.sqlalchemy_url)
            if normalized != self.sqlalchemy_url:
                object.__setattr__(self, "sqlalchemy_url", normalized)


@dataclass(frozen=True, slots=True)
class ServerSettings:
    """Stable server settings shared by the CLI and application factory."""

    name: str = DEFAULT_SERVER_NAME
    instructions: str = DEFAULT_SERVER_INSTRUCTIONS
    host: str = "127.0.0.1"
    port: int = 8000
    mount_path: str = "/"
    streamable_http_path: str = "/mcp"
    json_response: bool = True
    stateless_http: bool = True
    project_root: Path = DEFAULT_PROJECT_ROOT
    browser_search_config_path: Path = DEFAULT_BROWSER_CONFIG_PATH
    logging_config_path: Path = DEFAULT_LOGGING_CONFIG_PATH
    render_output_dir: Path = DEFAULT_RENDER_OUTPUT_DIR
    sessions_dir: Path = DEFAULT_SESSIONS_DIR
    browser_search: BrowserSearchSettings = field(default_factory=BrowserSearchSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)


def load_server_settings() -> ServerSettings:
    """Load server settings from environment variables with validated defaults."""
    project_root = _resolve_project_root()

    browser_search_config_path = _resolve_path_env(
        "MCP_BROWSER_CONFIG_PATH", project_root / "config" / "browser_search.yaml", project_root
    )
    browser_search_config = _load_yaml_config(browser_search_config_path)

    logging_config_path = _resolve_path_env(
        "MCP_LOGGING_CONFIG_PATH", project_root / "config" / "logging.yaml", project_root
    )
    logging_config = _load_yaml_config(logging_config_path)

    return ServerSettings(
        name=os.getenv("MCP_SERVER_NAME", DEFAULT_SERVER_NAME),
        instructions=os.getenv("MCP_SERVER_INSTRUCTIONS", DEFAULT_SERVER_INSTRUCTIONS),
        host=os.getenv("MCP_SERVER_HOST", "127.0.0.1"),
        port=_read_positive_int_env("MCP_SERVER_PORT", 8000),
        mount_path=os.getenv("MCP_SERVER_MOUNT_PATH", "/"),
        streamable_http_path=os.getenv("MCP_SERVER_STREAMABLE_HTTP_PATH", "/mcp"),
        project_root=project_root,
        browser_search_config_path=browser_search_config_path,
        logging_config_path=logging_config_path,
        render_output_dir=_resolve_path_env(
            "MCP_RENDER_OUTPUT_DIR", Path("runtime/render"), project_root
        ),
        sessions_dir=_resolve_path_env("MCP_SESSIONS_DIR", Path("runtime/sessions"), project_root),
        browser_search=_load_browser_search_settings(browser_search_config, project_root),
        logging=_load_logging_settings(logging_config, project_root),
        database=_load_database_settings(),
    )


def _read_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment for runtime settings."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}.") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer, got {parsed}.")
    return parsed


def _resolve_project_root() -> Path:
    """Resolve the project root used for config and runtime paths."""
    configured_root = os.getenv("MCP_PROJECT_ROOT")
    if configured_root is None:
        return DEFAULT_PROJECT_ROOT

    resolved_root = Path(configured_root).expanduser().resolve()
    if not resolved_root.exists():
        raise ValueError(f"MCP_PROJECT_ROOT does not exist: {resolved_root}")
    return resolved_root


def _resolve_path_env(env_name: str, default: Path, project_root: Path) -> Path:
    """Resolve a path from an environment variable or a default."""
    configured = os.getenv(env_name)
    if configured is None:
        if default.is_absolute():
            return default
        return (project_root / default).resolve()

    return _resolve_path(project_root, configured)


def _load_yaml_config(config_path: Path) -> dict[str, object]:
    """Load structured configuration from YAML if it exists."""
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file {config_path} must be a mapping.")
    return loaded


def _load_browser_search_settings(
    config_data: dict[str, object],
    project_root: Path,
) -> BrowserSearchSettings:
    """Merge browser search settings from YAML and environment variables."""
    browser_config = _read_mapping(config_data, "browser")
    cache_config = _read_mapping(config_data, "cache")
    filter_config = _read_mapping(config_data, "filter")

    return BrowserSearchSettings(
        browser=BrowserSettings(
            headless=_read_bool_setting(
                env_name="MCP_BROWSER_HEADLESS",
                config_value=browser_config.get("headless"),
                default=True,
            ),
            timeout_ms=_read_positive_int_setting(
                env_name="MCP_BROWSER_TIMEOUT_MS",
                config_value=browser_config.get("timeout_ms"),
                default=15_000,
            ),
            session_ttl_sec=_read_positive_int_setting(
                env_name="MCP_BROWSER_SESSION_TTL_SEC",
                config_value=browser_config.get("session_ttl_sec"),
                default=600,
            ),
            default_provider=_read_provider_setting(
                env_name="MCP_BROWSER_DEFAULT_PROVIDER",
                config_value=browser_config.get("default_provider"),
                default="bing",
            ),
            max_results=_read_positive_int_setting(
                env_name="MCP_BROWSER_MAX_RESULTS",
                config_value=browser_config.get("max_results"),
                default=5,
            ),
            user_agent=_read_optional_string_setting(
                env_name="MCP_BROWSER_USER_AGENT",
                config_value=browser_config.get("user_agent"),
                default=None,
            ),
        ),
        cache=SearchCacheSettings(
            enabled=_read_bool_setting(
                env_name="MCP_BROWSER_CACHE_ENABLED",
                config_value=cache_config.get("enabled"),
                default=True,
            ),
            ttl_sec=_read_positive_int_setting(
                env_name="MCP_BROWSER_CACHE_TTL_SEC",
                config_value=cache_config.get("ttl_sec"),
                default=1_800,
            ),
            base_dir=_read_path_setting(
                env_name="MCP_BROWSER_CACHE_BASE_DIR",
                config_value=cache_config.get("base_dir"),
                default=project_root / "runtime" / "cache" / "browser-search",
                project_root=project_root,
            ),
            max_entries=_read_positive_int_setting(
                env_name="MCP_BROWSER_CACHE_MAX_ENTRIES",
                config_value=cache_config.get("max_entries"),
                default=256,
            ),
        ),
        filter=SearchFilterSettings(
            ads_enabled=_read_bool_setting(
                env_name="MCP_BROWSER_FILTER_ADS_ENABLED",
                config_value=filter_config.get("ads_enabled"),
                default=True,
            ),
            strict_natural_results_only=_read_bool_setting(
                env_name="MCP_BROWSER_FILTER_STRICT_NATURAL_RESULTS_ONLY",
                config_value=filter_config.get("strict_natural_results_only"),
                default=False,
            ),
        ),
    )


def _load_logging_settings(
    config_data: dict[str, object],
    project_root: Path,
) -> LoggingSettings:
    """Merge logging settings from YAML and environment variables."""
    console_config = _read_mapping(config_data, "console")
    file_config = _read_mapping(config_data, "file")
    tool_config = _read_mapping(config_data, "tool")

    level = _read_optional_string_setting(
        env_name="MCP_LOG_LEVEL",
        config_value=config_data.get("level"),
        default="INFO",
    ).upper()
    if level not in VALID_LOG_LEVELS:
        raise ValueError(f"MCP_LOG_LEVEL must be one of {VALID_LOG_LEVELS}, got {level!r}.")

    return LoggingSettings(
        level=level,
        console_enabled=_read_bool_setting(
            env_name="MCP_LOG_CONSOLE_ENABLED",
            config_value=console_config.get("enabled"),
            default=True,
        ),
        console_color_enabled=_read_bool_setting(
            env_name="MCP_LOG_CONSOLE_COLOR",
            config_value=console_config.get("color"),
            default=True,
        ),
        file_enabled=_read_bool_setting(
            env_name="MCP_LOG_FILE_ENABLED",
            config_value=file_config.get("enabled"),
            default=True,
        ),
        file_path=_read_path_setting(
            env_name="MCP_LOG_FILE_PATH",
            config_value=file_config.get("path"),
            default=project_root / "runtime" / "logs" / "mcp-server.log",
            project_root=project_root,
        ),
        retention_days=_read_positive_int_setting(
            env_name="MCP_LOG_RETENTION_DAYS",
            config_value=file_config.get("retention_days"),
            default=14,
        ),
        tool_args_enabled=_read_bool_setting(
            env_name="MCP_LOG_TOOL_ARGS",
            config_value=tool_config.get("args_enabled"),
            default=False,
        ),
        max_field_length=_read_positive_int_setting(
            env_name="MCP_LOG_MAX_FIELD_LENGTH",
            config_value=tool_config.get("max_field_length"),
            default=100,
        ),
    )


def _load_database_settings() -> DatabaseSettings:
    """Load database settings exclusively from environment variables."""
    enabled = _read_bool_setting("MCP_DATABASE_ENABLED", None, False)
    raw_url = os.getenv("MCP_DATABASE_URL") or os.getenv("DATABASE_URL")

    if enabled and not raw_url:
        raise ValueError("MCP_DATABASE_ENABLED is true but no DATABASE_URL is set.")

    sqlalchemy_url = None
    if raw_url:
        enabled = True  # Auto-enable if URL is provided
        sqlalchemy_url = _normalize_sqlalchemy_url(raw_url)

    return DatabaseSettings(
        enabled=enabled,
        sqlalchemy_url=sqlalchemy_url,
        echo=_read_bool_setting("MCP_DATABASE_ECHO", None, False),
        pool_size=_read_positive_int_setting("MCP_DATABASE_POOL_SIZE", None, 5),
        max_overflow=_read_positive_int_setting("MCP_DATABASE_MAX_OVERFLOW", None, 10),
    )


def _normalize_sqlalchemy_url(url: str) -> str:
    """Ensure the database URL uses an async driver."""
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _read_mapping(config_data: dict[str, object], key: str) -> dict[str, object]:
    """Read a mapping from YAML config data and validate its shape."""
    value = config_data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{key}' must be a mapping.")
    return value


def _read_bool_setting(env_name: str, config_value: object, default: bool) -> bool:
    """Read a boolean from env vars or YAML config."""
    env_value = os.getenv(env_name)
    if env_value is not None:
        return _parse_bool(env_name, env_value)
    if config_value is None:
        return default
    if isinstance(config_value, bool):
        return config_value
    if isinstance(config_value, str):
        return _parse_bool(env_name, config_value)
    raise ValueError(f"{env_name} must be a boolean-compatible value.")


def _read_positive_int_setting(env_name: str, config_value: object, default: int) -> int:
    """Read a positive integer from env vars or YAML config."""
    env_value = os.getenv(env_name)
    if env_value is not None:
        return _parse_positive_int(env_name, env_value)
    if config_value is None:
        return default
    return _parse_positive_int(env_name, config_value)


def _read_optional_string_setting(
    env_name: str,
    config_value: object,
    default: str | None,
) -> str | None:
    """Read an optional string from env vars or YAML config."""
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value or None
    if config_value is None:
        return default
    if not isinstance(config_value, str):
        raise ValueError(f"{env_name} must be a string when configured.")
    return config_value or None


def _read_provider_setting(
    env_name: str,
    config_value: object,
    default: ProviderName,
) -> ProviderName:
    """Read a supported provider name from env vars or YAML config."""
    env_value = os.getenv(env_name)
    candidate = env_value if env_value is not None else config_value
    if candidate is None:
        return default
    if candidate != "bing":
        raise ValueError(f"{env_name} only supports 'bing' in the current version.")
    return "bing"


def _read_path_setting(
    env_name: str,
    config_value: object,
    default: Path,
    project_root: Path,
) -> Path:
    """Read a filesystem path from env vars or YAML config."""
    env_value = os.getenv(env_name)
    if env_value is not None:
        return _resolve_path(project_root, env_value)
    if config_value is None:
        return default
    if not isinstance(config_value, str):
        raise ValueError(f"{env_name} must be a path string when configured.")
    return _resolve_path(project_root, config_value)


def _resolve_path(project_root: Path, configured_path: str) -> Path:
    """Resolve a configurable path relative to the project root when needed."""
    raw_path = Path(configured_path).expanduser()
    return raw_path.resolve() if raw_path.is_absolute() else (project_root / raw_path).resolve()


def _parse_bool(name: str, value: object) -> bool:
    """Parse a boolean-like value from config sources."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{name} must be a boolean value, got {value!r}.")


def _parse_positive_int(name: str, value: object) -> int:
    """Parse a positive integer from config sources."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}.") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer, got {parsed}.")
    return parsed
