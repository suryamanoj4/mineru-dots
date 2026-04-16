#!/usr/bin/env python3
import glob
import json
import os
import subprocess
import sys

from mineru.cli.models_download import configure_model, has_pipeline_models
from mineru.utils.config_reader import get_local_models_dir
from mineru.utils.enum_class import ModelPath


DEFAULT_CONFIG_TEMPLATE = {
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


def set_default_env(var_name: str, default: str) -> str:
    value = os.getenv(var_name) or default
    os.environ[var_name] = value
    return value


def get_config_path() -> str:
    config_name = os.getenv("MINERU_TOOLS_CONFIG_JSON") or "mineru.json"
    if os.path.isabs(config_name):
        return config_name
    return os.path.join(os.path.expanduser("~"), config_name)


def ensure_config_file() -> None:
    config_path = get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.exists(config_path):
        return
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(DEFAULT_CONFIG_TEMPLATE, config_file, ensure_ascii=False, indent=4)


def requested_model_types(prefetch_value: str) -> list[str]:
    value = prefetch_value.strip().lower()
    if value in {"", "none"}:
        return []
    if value == "all":
        return ["pipeline", "vlm"]

    ordered: list[str] = []
    for part in (item.strip() for item in value.split(",")):
        if not part:
            continue
        if part not in {"pipeline", "vlm"}:
            raise SystemExit(
                f"[docker-startup] Unsupported MINERU_PREFETCH_MODELS value: {prefetch_value}"
            )
        if part not in ordered:
            ordered.append(part)
    return ordered


def has_vlm_models(model_dir: str | None) -> bool:
    if not model_dir or not os.path.isdir(model_dir):
        return False

    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path):
        return False

    for pattern in ("*.safetensors", "*.bin", "*.pt"):
        if glob.glob(os.path.join(model_dir, pattern)):
            return True
    return False


def has_models(model_type: str, model_dir: str | None) -> bool:
    if model_type == "pipeline":
        return has_pipeline_models(model_dir)
    if model_type == "vlm":
        return has_vlm_models(model_dir)
    raise SystemExit(f"[docker-startup] Unsupported model type: {model_type}")


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
        raise SystemExit(
            f"[docker-startup] Unsupported MINERU_MODEL_SOURCE value: {model_source}"
        )

    candidates = [path for path in glob.glob(pattern) if os.path.isdir(path)]
    return sorted(candidates, key=os.path.getmtime, reverse=True)


def configure_from_root(model_type: str, model_dir: str | None, label: str) -> bool:
    if not has_models(model_type, model_dir):
        return False
    print(f"[docker-startup] {label}: {model_type} -> {model_dir}")
    configure_model(model_dir, model_type)
    return True


def resolve_download_mode(prefetch_mode: str) -> str:
    if prefetch_mode in {"pipeline", "vlm", "all"}:
        return prefetch_mode
    if prefetch_mode in {"pipeline,vlm", "vlm,pipeline"}:
        return "all"
    raise SystemExit(
        f"[docker-startup] Unsupported MINERU_PREFETCH_MODELS value: {prefetch_mode}"
    )


def ensure_required_models(prefetch_mode: str) -> None:
    requested = requested_model_types(prefetch_mode)
    configured_roots = get_local_models_dir() or {}
    model_source = os.environ["MINERU_MODEL_SOURCE"]

    missing: list[str] = []
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

    if not missing:
        print("[docker-startup] Required models are already available in mounted volumes.")
        return

    download_mode = resolve_download_mode(prefetch_mode)
    if model_source == "local":
        raise SystemExit(
            f"[docker-startup] Missing local model configuration for {download_mode}."
        )

    print(
        f"[docker-startup] Downloading {download_mode} models into mounted cache volumes..."
    )
    subprocess.run(
        ["mineru-models-download", "-s", model_source, "-m", download_mode],
        check=True,
    )


def configured_model_exists() -> bool:
    models_dir = get_local_models_dir() or {}
    return bool(models_dir.get("pipeline") or models_dir.get("vlm"))


def main(argv: list[str]) -> int:
    set_default_env("MINERU_MODEL_SOURCE", "huggingface")
    prefetch_mode = set_default_env("MINERU_PREFETCH_MODELS", "none").lower()

    ensure_config_file()

    if prefetch_mode != "none":
        ensure_required_models(prefetch_mode)

    if configured_model_exists():
        os.environ["MINERU_MODEL_SOURCE"] = "local"

    if not argv:
        raise SystemExit("[docker-startup] No command provided to start-with-models.py")

    os.execvpe(argv[0], argv, os.environ)


if __name__ == "__main__":
    main(sys.argv[1:])
