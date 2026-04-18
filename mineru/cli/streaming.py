"""Backward-compatible shim for ``vparse.cli.streaming``."""

import sys

from vparse.cli import streaming as _streaming


sys.modules[__name__] = _streaming
