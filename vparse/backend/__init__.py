# Copyright (c) Opendatalab. All rights reserved.

from .base import BackendProtocol
from .registry import BackendRegistry

__all__ = [
    "BackendProtocol",
    "BackendRegistry",
]
