# Copyright (c) Opendatalab. All rights reserved.
"""Shared constants for public library and CLI entrypoints."""

AVAILABLE_BACKENDS: tuple[str, ...] = (
    "pipeline",
    "lite",
    "vlm-http-client",
    "hybrid-http-client",
    "vlm-auto-engine",
    "hybrid-auto-engine",
)
