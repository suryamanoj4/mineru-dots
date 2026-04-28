"""Backward-compatible shim for ``vparse.backend.lite.lite_analyze``."""

import sys

from vparse.backend.lite import lite_analyze as _lite_analyze


sys.modules[__name__] = _lite_analyze
