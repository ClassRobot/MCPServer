#!/usr/bin/env sh
set -eu

IMAGE_NAME="${IMAGE_NAME:-mcp-server:prod}"
CONTAINER_NAME="${CONTAINER_NAME:-mcp-server}"
HOST_PORT="${HOST_PORT:-8000}"
DATA_VOLUME="${DATA_VOLUME:-mcp-server-data}"
APT_DEBIAN_MIRROR="${APT_DEBIAN_MIRROR:-}"
APT_DEBIAN_SECURITY_MIRROR="${APT_DEBIAN_SECURITY_MIRROR:-}"

docker_info="$(docker info 2>/dev/null)" || {
  echo "Docker is not available. Please start Docker and retry." >&2
  exit 1
}

if printf '%s\n' "$docker_info" | grep -Eq 'HTTP Proxy|HTTPS Proxy' \
  && printf '%s\n' "$docker_info" | grep -q '127.0.0.1:1080'; then
  echo "Warning: Docker is configured to use 127.0.0.1:1080 as proxy." >&2
  echo "If that proxy is not running, apt/Playwright downloads will fail." >&2
fi

build_args=""
if [ -n "$APT_DEBIAN_MIRROR" ]; then
  build_args="${build_args} --build-arg APT_DEBIAN_MIRROR=${APT_DEBIAN_MIRROR}"
fi
if [ -n "$APT_DEBIAN_SECURITY_MIRROR" ]; then
  build_args="${build_args} --build-arg APT_DEBIAN_SECURITY_MIRROR=${APT_DEBIAN_SECURITY_MIRROR}"
fi

# shellcheck disable=SC2086
docker build -t "$IMAGE_NAME" $build_args .

if docker ps -aq --filter "name=^/${CONTAINER_NAME}$" | grep -q .; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:8000" \
  -v "${DATA_VOLUME}:/data" \
  -e MCP_MARKITDOWN_ALLOWED_ROOTS="/app:/data" \
  -e MCP_MARKITDOWN_OUTPUT_DIR="/data/markitdown" \
  "$IMAGE_NAME"

docker ps --filter "name=^/${CONTAINER_NAME}$"
