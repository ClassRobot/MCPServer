FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY config ./config
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.13-slim-bookworm AS runtime

ARG APT_DEBIAN_MIRROR=""
ARG APT_DEBIAN_SECURITY_MIRROR=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    MCP_SERVER_HOST=0.0.0.0 \
    MCP_SERVER_PORT=8000 \
    MCP_PROJECT_ROOT=/app \
    MCP_BROWSER_CONFIG_PATH=/app/config/browser_search.yaml \
    MCP_BROWSER_CACHE_BASE_DIR=/data/cache/browser-search \
    MCP_MARKITDOWN_CONFIG_PATH=/app/config/markitdown.yaml \
    MCP_MARKITDOWN_ALLOWED_ROOTS=/app:/data \
    MCP_MARKITDOWN_OUTPUT_DIR=/data/markitdown \
    MCP_LOG_FILE_PATH=/data/logs/mcp-server.log \
    PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/config ./config
COPY --from=builder /app/pyproject.toml ./pyproject.toml
COPY --from=builder /app/README.md ./README.md

RUN if [ -n "${APT_DEBIAN_MIRROR}" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && if [ -n "${APT_DEBIAN_SECURITY_MIRROR}" ]; then \
        sed -i "s|http://deb.debian.org/debian-security|${APT_DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
        sed -i "s|http://security.debian.org/debian-security|${APT_DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home --home-dir /home/appuser appuser \
    && mkdir -p /data/cache/browser-search /data/logs /data/markitdown /ms-playwright \
    && chown -R appuser:appgroup /app /data /ms-playwright /opt/venv

USER appuser

EXPOSE 8000
VOLUME ["/data"]

CMD ["sh", "-c", "exec mcp-server --transport streamable-http --host \"${MCP_SERVER_HOST:-0.0.0.0}\" --port \"${MCP_SERVER_PORT:-8000}\""]
