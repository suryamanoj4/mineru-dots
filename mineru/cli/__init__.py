"""Backward-compatible CLI package alias to vparse.cli."""

import sys
import vparse.cli as _vparse_cli

sys.modules[__name__] = _vparse_cli
