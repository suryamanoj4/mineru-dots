# Copyright (c) Opendatalab. All rights reserved.
import asyncio
import os
import time

from loguru import logger

from .utils import (
    enable_custom_logits_processors,
    set_default_gpu_memory_utilization,
    set_lmdeploy_backend,
    mod_kwargs_by_device_type,
    estimate_vlm_batch_size,
)
from .model_output_to_middle_json import result_to_middle_json
from ...data.data_reader_writer import DataWriter
from vparse.utils.pdf_image_tools import load_images_from_pdf
from ...utils.check_sys_env import is_mac_os_version_supported
from ...utils.compat import get_env_with_legacy
from ...utils.config_reader import get_device

from ...utils.enum_class import ImageType
from ...utils.models_download_utils import auto_download_and_get_model_root_path


class ModelSingleton:
    _instance = None
    _models = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(
        self,
        backend: str,
        model_path: str | None,
        server_url: str | None,
        **kwargs,
    ):
        key = (backend, model_path, server_url)
        if key not in self._models:
            start_time = time.time()

            if not model_path:
                model_path = auto_download_and_get_model_root_path("/", "vlm")

            if backend in ("vllm", "dots-ocr-vllm", "remote"):
                from .dots_ocr_client import DotsOCRClient

                self._models[key] = DotsOCRClient(
                    backend="vllm-async-engine",
                    model_path=model_path,
                    server_url=server_url,
                    **kwargs,
                )
                elapsed = round(time.time() - start_time, 2)
                logger.info(f"get vllm predictor cost: {elapsed}s")
                return self._models[key]

            from mineru_vl_utils import MinerUClient as VParseClient

            model = None
            processor = None
            vllm_llm = None
            lmdeploy_engine = None
            vllm_async_llm = None
            batch_size = kwargs.get("batch_size", 0)
            max_concurrency = kwargs.get("max_concurrency", 100)
            http_timeout = kwargs.get("http_timeout", 600)
            server_headers = kwargs.get("server_headers", None)
            max_retries = kwargs.get("max_retries", 3)
            retry_backoff_factor = kwargs.get("retry_backoff_factor", 0.5)

            for param in [
                "batch_size",
                "max_concurrency",
                "http_timeout",
                "server_headers",
                "max_retries",
                "retry_backoff_factor",
            ]:
                if param in kwargs:
                    del kwargs[param]

            if backend == "mlx":
                mlx_supported = is_mac_os_version_supported()
                if not mlx_supported:
                    raise EnvironmentError(
                        "mlx backend is only supported on macOS 13.5+ with Apple Silicon."
                    )
                try:
                    from mlx_vlm import load as mlx_load
                except ImportError:
                    raise ImportError(
                        "Please install mlx-vlm to use the mlx backend."
                    )
                model, processor = mlx_load(model_path)
            else:
                if os.getenv("OMP_NUM_THREADS") is None:
                    os.environ["OMP_NUM_THREADS"] = "1"

                if backend == "lmdeploy":
                    try:
                        from lmdeploy import PytorchEngineConfig, TurbomindEngineConfig
                        from lmdeploy.serve.vl_async_engine import VLAsyncEngine
                    except ImportError:
                        raise ImportError(
                            "Please install lmdeploy to use the lmdeploy backend."
                        )
                    if "cache_max_entry_count" not in kwargs:
                        kwargs["cache_max_entry_count"] = 0.5

                    device_type = get_env_with_legacy("VPARSE_LMDEPLOY_DEVICE", "MINERU_LMDEPLOY_DEVICE", "")
                    if device_type == "":
                        if "lmdeploy_device" in kwargs:
                            device_type = kwargs.pop("lmdeploy_device")
                            if device_type not in ["cuda", "ascend", "maca", "camb"]:
                                raise ValueError(
                                    f"Unsupported lmdeploy device type: {device_type}"
                                )
                        else:
                            device_type = "cuda"
                    lm_backend = get_env_with_legacy("VPARSE_LMDEPLOY_BACKEND", "MINERU_LMDEPLOY_BACKEND", "")
                    if lm_backend == "":
                        if "lmdeploy_backend" in kwargs:
                            lm_backend = kwargs.pop("lmdeploy_backend")
                            if lm_backend not in ["pytorch", "turbomind"]:
                                raise ValueError(
                                    f"Unsupported lmdeploy backend: {lm_backend}"
                                )
                        else:
                            lm_backend = set_lmdeploy_backend(device_type)
                    logger.info(
                        f"lmdeploy device is: {device_type}, lmdeploy backend is: {lm_backend}"
                    )

                    if lm_backend == "pytorch":
                        kwargs["device_type"] = device_type
                        backend_config = PytorchEngineConfig(**kwargs)
                    elif lm_backend == "turbomind":
                        backend_config = TurbomindEngineConfig(**kwargs)
                    else:
                        raise ValueError(f"Unsupported lmdeploy backend: {lm_backend}")

                    log_level = "ERROR"
                    from lmdeploy.utils import get_logger

                    lm_logger = get_logger("lmdeploy")
                    lm_logger.setLevel(log_level)
                    if os.getenv("TM_LOG_LEVEL") is None:
                        os.environ["TM_LOG_LEVEL"] = log_level

                    lmdeploy_engine = VLAsyncEngine(
                        model_path,
                        backend=lm_backend,
                        backend_config=backend_config,
                    )

            self._models[key] = VParseClient(
                backend=backend,
                model=model,
                processor=processor,
                lmdeploy_engine=lmdeploy_engine,
                vllm_llm=vllm_llm,
                vllm_async_llm=vllm_async_llm,
                server_url=server_url,
                batch_size=batch_size,
                max_concurrency=max_concurrency,
                http_timeout=http_timeout,
                server_headers=server_headers,
                max_retries=max_retries,
                retry_backoff_factor=retry_backoff_factor,
            )
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"get {backend} predictor cost: {elapsed}s")
        return self._models[key]


async def _aio_doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="vllm",
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(
            backend, model_path, server_url, **kwargs
        )

    load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
    load_images_time = round(time.time() - load_images_start, 2)
    logger.debug(
        f"load images cost: {load_images_time}, speed: {round(len(images_pil_list) / load_images_time, 3)} images/s"
    )

    infer_start = time.time()
    results = await predictor.aio_batch_two_step_extract(
        images=images_pil_list, prompt_mode=prompt_mode
    )
    infer_time = round(time.time() - infer_start, 2)
    logger.debug(
        f"infer finished, cost: {infer_time}, speed: {round(len(results) / infer_time, 3)} page/s"
    )

    middle_json = result_to_middle_json(results, images_list, pdf_doc, image_writer)
    return middle_json, results


def sync_doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="vllm",
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    return asyncio.run(
        _aio_doc_analyze(
            pdf_bytes,
            image_writer=image_writer,
            predictor=predictor,
            backend=backend,
            model_path=model_path,
            server_url=server_url,
            prompt_mode=prompt_mode,
            **kwargs,
        )
    )


async def aio_doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="vllm",
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    return await _aio_doc_analyze(
        pdf_bytes,
        image_writer=image_writer,
        predictor=predictor,
        backend=backend,
        model_path=model_path,
        server_url=server_url,
        prompt_mode=prompt_mode,
        **kwargs,
    )


def doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="vllm",
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    return sync_doc_analyze(
        pdf_bytes,
        image_writer=image_writer,
        predictor=predictor,
        backend=backend,
        model_path=model_path,
        server_url=server_url,
        prompt_mode=prompt_mode,
        **kwargs,
    )


async def batch_doc_analyze(
    pdf_bytes_list: list[bytes],
    image_writers: list[DataWriter | None] | None = None,
    predictor=None,
    backend="vllm",
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    batch_size: int = 0,
    **kwargs,
):
    if predictor is None:
        predictor = ModelSingleton().get_model(
            backend, model_path, server_url, **kwargs
        )

    if image_writers is None:
        image_writers = [None] * len(pdf_bytes_list)

    if batch_size <= 0:
        batch_size = estimate_vlm_batch_size()

    load_start = time.time()

    page_tasks = [
        asyncio.to_thread(load_images_from_pdf, b, ImageType.PIL)
        for b in pdf_bytes_list
    ]
    all_results = await asyncio.gather(*page_tasks)

    books = []
    total_pages = 0
    for images_list, pdf_doc in all_results:
        pil_list = [d["img_pil"] for d in images_list]
        books.append((pil_list, images_list, pdf_doc))
        total_pages += len(pil_list)

    load_time = round(time.time() - load_start, 2)
    logger.info(
        f"loaded {total_pages} pages from {len(pdf_bytes_list)} docs in {load_time}s, "
        f"speed: {round(total_pages / load_time, 3)} pages/s"
    )

    book_page_ranges = []
    all_images = []
    offset = 0
    for pil_list, _, _ in books:
        book_page_ranges.append((offset, offset + len(pil_list)))
        all_images.extend(pil_list)
        offset += len(pil_list)

    infer_start = time.time()
    logger.info(
        f"batch inference: {total_pages} pages across {len(pdf_bytes_list)} docs, "
        f"batch_size={batch_size}"
    )

    all_blocks = []
    for batch_start in range(0, total_pages, batch_size):
        batch_end = min(batch_start + batch_size, total_pages)
        batch_images = all_images[batch_start:batch_end]
        batch_results = await predictor.aio_batch_two_step_extract(
            images=batch_images, prompt_mode=prompt_mode
        )
        all_blocks.extend(batch_results)
        logger.debug(
            f"batch [{batch_start}:{batch_end}] done, "
            f"speed: {round(len(batch_images) / (time.time() - infer_start + 0.001), 3)} pages/s"
        )

    infer_time = round(time.time() - infer_start, 2)
    logger.info(
        f"inference done in {infer_time}s, "
        f"speed: {round(total_pages / infer_time, 3)} pages/s"
    )

    post_start = time.time()
    middle_jsons = []
    model_outputs = []

    post_tasks = []
    for book_idx, (start, end) in enumerate(book_page_ranges):
        book_blocks = all_blocks[start:end]
        pil_list, images_list, pdf_doc = books[book_idx]
        writer = image_writers[book_idx] if image_writers and book_idx < len(image_writers) else None

        post_tasks.append(
            asyncio.to_thread(
                result_to_middle_json,
                book_blocks,
                images_list,
                pdf_doc,
                writer,
            )
        )

    middle_jsons = await asyncio.gather(*post_tasks)

    post_time = round(time.time() - post_start, 2)
    logger.info(f"post-processing done in {post_time}s")

    for idx, mj in enumerate(middle_jsons):
        _, _, end = book_page_ranges[idx]
        start = book_page_ranges[idx][0]
        model_outputs.append(all_blocks[start:end])

    return list(zip(middle_jsons, model_outputs))
