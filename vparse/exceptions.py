"""VParse exception hierarchy with backward-compatible MinerU aliases."""

import sys


class VParseError(Exception):
    """Base exception for VParse."""


MinerUError = VParseError


class BackendError(VParseError):
    """Raised when a backend cannot be initialized or used correctly."""


class ModelLoadError(BackendError):
    """Raised when a model cannot be loaded."""


class ConfigurationError(VParseError):
    """Raised when configuration is invalid."""


class InputError(VParseError):
    """Raised when input data or arguments are invalid."""


class ProcessingError(VParseError):
    """Raised when document processing fails."""


class TimeoutError(VParseError):
    """Raised when an operation exceeds the allowed time."""


__all__ = [
    "VParseError",
    "MinerUError",
    "BackendError",
    "ModelLoadError",
    "ConfigurationError",
    "InputError",
    "ProcessingError",
    "TimeoutError",
]


_module = sys.modules[__name__]
sys.modules.setdefault("vparse.exceptions", _module)
sys.modules.setdefault("mineru.exceptions", _module)
