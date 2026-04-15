#!/usr/bin/env python
# Entry point with spawn multiprocessing for vLLM compatibility
import os
import sys

# Set environment variable to force vLLM to use spawn method
# This must be set before importing vllm or initializing CUDA
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"

# Import main CLI command (needed for package entry point)
from vparse.cli.client import main


if __name__ == "__main__":
    sys.exit(main())
