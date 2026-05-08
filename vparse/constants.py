# Copyright (c) Opendatalab. All rights reserved.
"""Shared constants for public library and CLI entrypoints."""

from .backend.registry import BACKEND_ALIASES, BackendRegistry

AVAILABLE_BACKENDS: tuple[str, ...] = tuple(BackendRegistry.get_backend_names())
LEGACY_BACKEND_ALIASES: tuple[str, ...] = tuple(sorted(BACKEND_ALIASES))
ACCEPTED_BACKENDS: tuple[str, ...] = tuple(
    sorted(set(AVAILABLE_BACKENDS) | set(LEGACY_BACKEND_ALIASES))
)
