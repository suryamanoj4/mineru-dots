# Copyright (c) Opendatalab. All rights reserved.
import os

# Backward compatibility: allow legacy MINERU_* env vars when VPARSE_* is unset.
for env_key, env_value in list(os.environ.items()):
    if env_key.startswith("MINERU_"):
        vparse_key = f"VPARSE_{env_key[len('MINERU_'):]}"
        os.environ.setdefault(vparse_key, env_value)
