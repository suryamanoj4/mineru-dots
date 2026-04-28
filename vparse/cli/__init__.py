"""CLI package for vParse.

Keep package import side effects minimal so legacy import paths such as
``mineru.cli.models_download`` do not pull in optional runtime components.
"""

__all__: list[str] = []

import sys
_module = sys.modules[__name__]
sys.modules.setdefault("vparse.cli", _module)
sys.modules.setdefault("mineru.cli", _module)
