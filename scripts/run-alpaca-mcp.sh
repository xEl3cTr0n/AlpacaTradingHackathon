#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment_file="$repository_root/.env"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repository_root/backend/.uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-$repository_root/backend/.uv-tools}"
export UV_TOOL_BIN_DIR="${UV_TOOL_BIN_DIR:-$repository_root/backend/.uv-bin}"

if [[ ! -f "$environment_file" ]]; then
  echo "Missing $environment_file. Copy .env.example to .env and add paper credentials." >&2
  exit 1
fi

# Read only the values required by Alpaca. Do not source the file as shell code.
while IFS='=' read -r key value; do
  value="${value%$'\r'}"
  case "$key" in
    ALPACA_API_KEY | ALPACA_SECRET_KEY)
      export "$key=$value"
      ;;
  esac
done < "$environment_file"

: "${ALPACA_API_KEY:?ALPACA_API_KEY is missing from .env}"
: "${ALPACA_SECRET_KEY:?ALPACA_SECRET_KEY is missing from .env}"

# These are intentionally not configurable here: MCP access is paper-only and
# excludes mutation toolsets so agents cannot bypass the app's Risk Agent.
export ALPACA_PAPER_TRADE=true
export ALPACA_TOOLSETS="account,assets,stock-data,options-data,news,corporate-actions"

if command -v uvx >/dev/null 2>&1; then
  exec uvx alpaca-mcp-server
fi

workspace_uvx="$repository_root/backend/.venv/bin/uvx"
if [[ -x "$workspace_uvx" ]]; then
  exec "$workspace_uvx" alpaca-mcp-server
fi

echo "uvx is not installed. Install uv, then restart your MCP client." >&2
exit 127
