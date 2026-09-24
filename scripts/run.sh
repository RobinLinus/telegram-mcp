#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# A separately installed runtime survives desktop plugin cache updates.
python=${TELEGRAM_MCP_PYTHON:-"$HOME/.local/share/telegram-mcp/venv/bin/python"}
if [ ! -x "$python" ] && [ -x "$root/.venv/bin/python" ]; then
    python="$root/.venv/bin/python"
fi
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python" -m telegram_mcp.server
