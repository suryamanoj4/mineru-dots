"""Backward-compatible shim for ``vparse.backend.lite``."""

import sys

from vparse.backend import lite as _lite


sys.modules[__name__] = _lite
