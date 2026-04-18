# Copyright (c) Opendatalab. All rights reserved.

from .lite_analyze import doc_analyze

__all__ = ["doc_analyze"]

import sys
_module = sys.modules[__name__]
sys.modules.setdefault("vparse.backend.lite", _module)
sys.modules.setdefault("mineru.backend.lite", _module)
