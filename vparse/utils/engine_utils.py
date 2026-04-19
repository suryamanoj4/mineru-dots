#  Copyright (c) Opendatalab. All rights reserved.
from loguru import logger


def get_vlm_engine(inference_engine: str, is_async: bool = False) -> str:
    """
    Auto-select or verify the VLM inference engine (uses dots.ocr as default VLM model).

    Args:
        inference_engine: Specified engine name or 'auto' for automatic selection.
        is_async: Whether to use an asynchronous engine.

    Returns:
        Final selected engine name.
    """
    if inference_engine == "auto":
        inference_engine = "dots-ocr"

    formatted_engine = _format_engine_name(inference_engine, is_async)
    logger.info(f"Using {formatted_engine} as the inference engine for VLM (dots.ocr).")
    return formatted_engine


def _format_engine_name(engine: str, is_async: bool = False) -> str:
    """Uniformly format engine name."""
    if engine == "dots-ocr":
        return "dots-ocr-vllm"
    if engine != "transformers":
        if is_async and engine == "vllm":
            return "vllm-async-engine"
        return f"{engine}-engine"
    return engine
