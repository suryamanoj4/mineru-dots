"""Top-level package for VParse with MinerU compatibility aliases."""

from .exceptions import (
    BackendError,
    ConfigurationError,
    InputError,
    MinerUError,
    ModelLoadError,
    ProcessingError,
    TimeoutError,
    VParseError,
)
from .utils.compat import alias_legacy_env_vars
from .version import __version__

alias_legacy_env_vars()

__all__ = [
    "__version__",
    "VParseError",
    "MinerUError",
    "BackendError",
    "ModelLoadError",
    "ConfigurationError",
    "InputError",
    "ProcessingError",
    "TimeoutError",
]
