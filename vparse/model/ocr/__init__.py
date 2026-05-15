# Copyright (c) Opendatalab. All rights reserved.

from __future__ import annotations

import sys
from importlib import import_module

__all__ = ["PytorchPaddleOCR", "TesseractOCRModel"]

_LAZY_IMPORTS = {
    "PytorchPaddleOCR": (".pytorch_paddle", "PytorchPaddleOCR"),
    "TesseractOCRModel": (".tesseract", "TesseractOCRModel"),
}

_module = sys.modules[__name__]
sys.modules.setdefault("vparse.model.ocr", _module)
sys.modules.setdefault("mineru.model.ocr", _module)


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
