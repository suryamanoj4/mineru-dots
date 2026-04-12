#!/usr/bin/env bash
set -euo pipefail

export MINERU_MODEL_SOURCE="${MINERU_MODEL_SOURCE:-huggingface}"

if python3 - <<'PY'
import glob
import os
import sys

from mineru.cli.models_download import configure_model, has_pipeline_models
from mineru.utils.config_reader import get_local_models_dir
from mineru.utils.enum_class import ModelPath


def use_cached_pipeline_root(root, label):
    if has_pipeline_models(root):
        print(f"[cpu-startup] {label}: {root}")
        configure_model(root, "pipeline")
        sys.exit(0)


models_dir = get_local_models_dir() or {}
use_cached_pipeline_root(models_dir.get("pipeline"), "Using configured pipeline models")

model_source = os.getenv("MINERU_MODEL_SOURCE", "huggingface")
candidates = []
if model_source == "huggingface":
    repo_name = ModelPath.pipeline_root_hf.replace("/", "--")
    candidates = sorted(
        glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{repo_name}/snapshots/*")),
        reverse=True,
    )
elif model_source == "modelscope":
    repo_name = ModelPath.pipeline_root_modelscope
    candidates = sorted(
        glob.glob(os.path.expanduser(f"~/.cache/modelscope/hub/{repo_name}*")),
        reverse=True,
    )

for candidate in candidates:
    use_cached_pipeline_root(candidate, "Using cached pipeline models")

sys.exit(1)
PY
then
    echo "[cpu-startup] Pipeline models already available. Skipping download."
else
    echo "[cpu-startup] Preparing pipeline models before starting Gradio..."
    mineru-models-download -s "${MINERU_MODEL_SOURCE}" -m pipeline
fi

export MINERU_MODEL_SOURCE=local

exec mineru-gradio "$@"
