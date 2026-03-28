#!/usr/bin/env python
# Entry point with spawn multiprocessing for vLLM compatibility
import os
import sys

# Set environment variable to force vLLM to use spawn method
# This must be set before importing vllm or initializing CUDA
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"


if __name__ == "__main__":
    # Import and run the actual CLI
    from mineru.cli.client import main

    sys.exit(main())
