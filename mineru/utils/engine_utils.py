#  Copyright (c) Opendatalab. All rights reserved.
from loguru import logger


def get_vlm_engine(inference_engine: str, is_async: bool = False) -> str:
    """
    自动选择或验证 VLM 推理引擎 (使用 dots.ocr 作为 default VLM model)

    Args:
        inference_engine: 指定的引擎名称或 'auto' 进行自动选择
        is_async: 是否使用异步引擎

    Returns:
        最终选择的引擎名称
    """
    if inference_engine == "auto":
        inference_engine = "dots-ocr"

    formatted_engine = _format_engine_name(inference_engine, is_async)
    logger.info(f"Using {formatted_engine} as the inference engine for VLM (dots.ocr).")
    return formatted_engine


def _format_engine_name(engine: str, is_async: bool = False) -> str:
    """统一格式化引擎名称"""
    if engine == "dots-ocr":
        return "dots-ocr-vllm"
    if engine != "transformers":
        if is_async and engine == "vllm":
            return "vllm-async-engine"
        return f"{engine}-engine"
    return engine
