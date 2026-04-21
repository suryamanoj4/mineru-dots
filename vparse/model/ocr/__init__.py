# Copyright (c) Opendatalab. All rights reserved.

from .pytorch_paddle import PytorchPaddleOCR
from .tesseract import TesseractOCRModel

__all__ = ["PytorchPaddleOCR", "TesseractOCRModel"]

import sys
_module = sys.modules[__name__]
sys.modules.setdefault("vparse.model.ocr", _module)
sys.modules.setdefault("mineru.model.ocr", _module)
