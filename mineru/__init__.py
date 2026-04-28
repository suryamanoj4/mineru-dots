"""Backward-compatible alias package for the vparse rebrand."""

import sys
import vparse as _vparse

# Keep `import mineru` working by aliasing to the vparse package object.
sys.modules[__name__] = _vparse
