#!/usr/bin/env bash
set -euo pipefail

export VPARSE_PREFETCH_MODELS="${VPARSE_PREFETCH_MODELS:-${MINERU_PREFETCH_MODELS:-pipeline}}"
exec python3 /app/docker/global/start-with-models.py vparse-gradio "$@"
