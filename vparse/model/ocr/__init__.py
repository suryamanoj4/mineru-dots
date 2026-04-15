# Copyright (c) Opendatalab. All rights reserved.

from .pytorch_paddle import PytorchPaddleOCR
from .tesseract import TesseractOCRModel

__all__ = ["PytorchPaddleOCR", "TesseractOCRModel"]
