#!/usr/bin/env bash
# Sobe o agente de terminal no ambiente de desenvolvimento.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AGENTE_BASE="$DIR"
exec "$DIR/.venv/bin/python" -m hrx_code "$@"
