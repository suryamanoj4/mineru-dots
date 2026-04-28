"""Backward-compatible shim for ``vparse.model.ocr.tesseract``."""

import sys

from vparse.model.ocr import tesseract as _tesseract


sys.modules[__name__] = _tesseract
