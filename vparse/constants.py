# Copyright (c) Opendatalab. All rights reserved.
"""Shared constants for public library and CLI entrypoints."""

from .backend.registry import BackendRegistry

AVAILABLE_BACKENDS: tuple[str, ...] = tuple(BackendRegistry.get_backend_names())
