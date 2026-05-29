"""Top-level package for VParse with MinerU compatibility aliases."""

from .async_client import AsyncVParse
from .client import VParse
from .config import Config
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
from .result import BlockInfo, OCRResult, PageInfo
from .backend import BackendProtocol, BackendRegistry
from .utils.compat import alias_legacy_env_vars
from .version import __version__

alias_legacy_env_vars()

__all__ = [
    "__version__",
    "VParse",
    "AsyncVParse",
    "Config",
    "BackendProtocol",
    "BackendRegistry",
    "OCRResult",
    "PageInfo",
    "BlockInfo",
    "VParseError",
    "MinerUError",
    "BackendError",
    "ModelLoadError",
    "ConfigurationError",
    "InputError",
    "ProcessingError",
    "TimeoutError",
]
