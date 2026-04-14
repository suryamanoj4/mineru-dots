#!/usr/bin/env bash
set -euo pipefail

export MINERU_PREFETCH_MODELS="${MINERU_PREFETCH_MODELS:-pipeline}"
exec /app/docker/global/start-with-models.sh mineru-gradio "$@"
