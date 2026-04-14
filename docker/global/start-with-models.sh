#!/usr/bin/env bash
set -euo pipefail

export MINERU_MODEL_SOURCE="${MINERU_MODEL_SOURCE:-huggingface}"
export MINERU_PREFETCH_MODELS="${MINERU_PREFETCH_MODELS:-none}"

if [[ -n "${MINERU_TOOLS_CONFIG_JSON:-}" && "${MINERU_TOOLS_CONFIG_JSON}" = /* ]]; then
    mkdir -p "$(dirname "${MINERU_TOOLS_CONFIG_JSON}")"
fi

python3 - <<'PY'
import json
import os


config_name = os.getenv("MINERU_TOOLS_CONFIG_JSON", "mineru.json")
if os.path.isabs(config_name):
    config_path = config_name
else:
    config_path = os.path.join(os.path.expanduser("~"), config_name)

os.makedirs(os.path.dirname(config_path), exist_ok=True)

if not os.path.exists(config_path):
    template = {
        "bucket_info": {
            "bucket-name-1": ["ak", "sk", "endpoint"],
            "bucket-name-2": ["ak", "sk", "endpoint"],
        },
        "latex-delimiter-config": {
            "display": {"left": "$$", "right": "$$"},
            "inline": {"left": "$", "right": "$"},
        },
        "llm-aided-config": {
            "title_aided": {
                "api_key": "your_api_key",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen3-next-80b-a3b-instruct",
                "enable_thinking": False,
                "enable": False,
            }
        },
        "models-dir": {"pipeline": "", "vlm": ""},
        "config_version": "1.3.1",
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=4)
PY

prefetch_mode="${MINERU_PREFETCH_MODELS,,}"

if [[ "${prefetch_mode}" != "none" ]]; then
    if python3 - <<'PY'
import glob
import os
import sys

from mineru.cli.models_download import configure_model, has_pipeline_models
from mineru.utils.config_reader import get_local_models_dir
from mineru.utils.enum_class import ModelPath


def requested_model_types(prefetch_value: str) -> list[str]:
    value = prefetch_value.strip().lower()
    if value in {"", "none"}:
        return []
    if value == "all":
        return ["pipeline", "vlm"]
    parts = [part.strip() for part in value.split(",") if part.strip()]
    ordered = []
    for part in parts:
        if part not in {"pipeline", "vlm"}:
            raise ValueError(f"Unsupported MINERU_PREFETCH_MODELS value: {prefetch_value}")
        if part not in ordered:
            ordered.append(part)
    return ordered


def has_vlm_models(model_dir: str | None) -> bool:
    if not model_dir or not os.path.isdir(model_dir):
        return False

    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path):
        return False

    weight_patterns = ("*.safetensors", "*.bin", "*.pt")
    for pattern in weight_patterns:
        if glob.glob(os.path.join(model_dir, pattern)):
            return True
    return False


def has_models(model_type: str, model_dir: str | None) -> bool:
    if model_type == "pipeline":
        return has_pipeline_models(model_dir)
    if model_type == "vlm":
        return has_vlm_models(model_dir)
    raise ValueError(f"Unsupported model type: {model_type}")


def cache_candidates(model_type: str, model_source: str) -> list[str]:
    if model_source == "local":
        return []

    if model_source == "huggingface":
        repo_name = {
            "pipeline": ModelPath.pipeline_root_hf,
            "vlm": ModelPath.vlm_root_hf,
        }[model_type].replace("/", "--")
        pattern = os.path.expanduser(
            f"~/.cache/huggingface/hub/models--{repo_name}/snapshots/*"
        )
    elif model_source == "modelscope":
        repo_name = {
            "pipeline": ModelPath.pipeline_root_modelscope,
            "vlm": ModelPath.vlm_root_modelscope,
        }[model_type]
        pattern = os.path.expanduser(f"~/.cache/modelscope/hub/{repo_name}*")
    else:
        raise ValueError(f"Unsupported MINERU_MODEL_SOURCE value: {model_source}")

    candidates = [path for path in glob.glob(pattern) if os.path.isdir(path)]
    return sorted(candidates, key=os.path.getmtime, reverse=True)


def configure_from_root(model_type: str, model_dir: str | None, label: str) -> bool:
    if has_models(model_type, model_dir):
        print(f"[docker-startup] {label}: {model_type} -> {model_dir}")
        configure_model(model_dir, model_type)
        return True
    return False


model_source = os.getenv("MINERU_MODEL_SOURCE", "huggingface")
prefetch = os.getenv("MINERU_PREFETCH_MODELS", "none")
requested = requested_model_types(prefetch)
configured_roots = get_local_models_dir() or {}

missing = []
for model_type in requested:
    if configure_from_root(
        model_type,
        configured_roots.get(model_type),
        "Using configured models",
    ):
        continue

    for candidate in cache_candidates(model_type, model_source):
        if configure_from_root(model_type, candidate, "Using cached models"):
            break
    else:
        missing.append(model_type)

if missing:
    print(
        f"[docker-startup] Missing required model caches for: {', '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
    then
        echo "[docker-startup] Required models are already available in mounted volumes."
    else
        case "${prefetch_mode}" in
            pipeline|vlm|all)
                download_mode="${prefetch_mode}"
                ;;
            pipeline,vlm|vlm,pipeline)
                download_mode="all"
                ;;
            *)
                echo "[docker-startup] Unsupported MINERU_PREFETCH_MODELS value: ${MINERU_PREFETCH_MODELS}" >&2
                exit 1
                ;;
        esac

        if [[ "${MINERU_MODEL_SOURCE}" == "local" ]]; then
            echo "[docker-startup] Missing local model configuration for ${download_mode}." >&2
            exit 1
        fi

        echo "[docker-startup] Downloading ${download_mode} models into mounted cache volumes..."
        mineru-models-download -s "${MINERU_MODEL_SOURCE}" -m "${download_mode}"
    fi
fi

if python3 - <<'PY'
import sys

from mineru.utils.config_reader import get_local_models_dir

models_dir = get_local_models_dir() or {}
sys.exit(0 if models_dir.get("pipeline") or models_dir.get("vlm") else 1)
PY
then
    export MINERU_MODEL_SOURCE=local
fi

exec "$@"
