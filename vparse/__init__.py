"""Top-level package for VParse with MinerU compatibility aliases."""

from __future__ import annotations

from importlib import import_module

from .integrations import scan_prescription_image
from .utils.compat import alias_legacy_env_vars
from .version import __version__

alias_legacy_env_vars()

_LAZY_IMPORTS = {
    "AsyncVParse": (".async_client", "AsyncVParse"),
    "VParse": (".client", "VParse"),
    "Config": (".config", "Config"),
    "BackendProtocol": (".backend", "BackendProtocol"),
    "BackendRegistry": (".backend", "BackendRegistry"),
    "OCRResult": (".result", "OCRResult"),
    "PageInfo": (".result", "PageInfo"),
    "BlockInfo": (".result", "BlockInfo"),
    "VParseError": (".exceptions", "VParseError"),
    "MinerUError": (".exceptions", "MinerUError"),
    "BackendError": (".exceptions", "BackendError"),
    "ModelLoadError": (".exceptions", "ModelLoadError"),
    "ConfigurationError": (".exceptions", "ConfigurationError"),
    "InputError": (".exceptions", "InputError"),
    "ProcessingError": (".exceptions", "ProcessingError"),
    "TimeoutError": (".exceptions", "TimeoutError"),
}

__all__ = [
    "__version__",
    "VParse",
    "AsyncVParse",
    "Config",
    "BackendProtocol",
    "BackendRegistry",
    "scan_prescription_image",
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


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
