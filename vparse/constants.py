# Copyright (c) Opendatalab. All rights reserved.
"""Shared constants for public library and CLI entrypoints."""

AVAILABLE_BACKENDS: tuple[str, ...] = (
    "pipeline",
    "lite",
    "vlm",
    "vlm-lmdeploy",
    "hybrid",
    "hybrid-lmdeploy",
    "remote",
)
