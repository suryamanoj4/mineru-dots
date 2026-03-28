#!/usr/bin/env python
# Entry point with spawn multiprocessing for vLLM compatibility
import multiprocessing
import sys

# MUST be set before any other imports that might initialize CUDA
try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass

# Import and run the actual CLI
from mineru.cli.client import main

sys.exit(main())
