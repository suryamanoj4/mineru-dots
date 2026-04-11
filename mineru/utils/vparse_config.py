from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class ApiServerConfig(BaseModel):
    host: str
    port: int
    workers: int
    max_concurrent_requests: int


class EngineConfig(BaseModel):
    active: bool
    model_name: str
    inference_backend: str
    port: int
    trust_remote_code: bool
    max_model_len: Literal["auto"] | int
    gpu_memory_utilization: Literal["auto"] | float


class RemoteNodesConfig(BaseModel):
    vlm_server_url: str


class VParseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_server: ApiServerConfig
    engine: EngineConfig
    remote_nodes: RemoteNodesConfig


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "vparse_config.yaml"


def load_config(config_path: str | Path | None = None) -> VParseConfig:
    path = Path(config_path) if config_path else _default_config_path()

    if not path.exists():
        raise FileNotFoundError(f"vParse config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid vParse config format in {path}: expected a YAML mapping")

    try:
        return VParseConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid vParse config in {path}: {exc}") from exc


config = load_config()
