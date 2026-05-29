from loguru import logger

from ..backend.vlm.utils import resolve_vlm_engine


def get_vlm_engine(inference_engine: str, is_async: bool = False) -> str:
    if inference_engine == "auto":
        return resolve_vlm_engine()
    return inference_engine
