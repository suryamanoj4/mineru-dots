#!/usr/bin/env bash
set -euo pipefail

export MINERU_MODEL_SOURCE="${MINERU_MODEL_SOURCE:-huggingface}"

echo "[cpu-startup] Preparing pipeline models before starting Gradio..."
mineru-models-download -s "${MINERU_MODEL_SOURCE}" -m pipeline

export MINERU_MODEL_SOURCE=local

exec mineru-gradio "$@"
