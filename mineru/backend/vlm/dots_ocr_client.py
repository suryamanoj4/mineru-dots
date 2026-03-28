import time
from typing import List, Optional

from loguru import logger

from .dots_ocr.utils.layout_utils import post_process_output
from .dots_ocr.utils.prompts import dict_promptmode_to_prompt
from mineru_vl_utils import MinerUClient, MinerUSamplingParams
from mineru_vl_utils.structs import ContentBlock


DOTS_TO_MINERU_TYPE = {
    "Text": "text",
    "Title": "title",
    "Caption": "image_caption",
    "Table": "table",
    "Picture": "image",
    "Formula": "equation",
    "Section-header": "title",
    "List-item": "list",
    "Page-header": "header",
    "Page-footer": "footer",
    "Footnote": "page_footnote",
}


class DotsOCRClient:
    def __init__(
        self,
        backend: str = "transformers",
        model_path: Optional[str] = None,
        server_url: Optional[str] = None,
        use_hf: bool = False,
        temperature: float = 0.1,
        top_p: float = 1.0,
        max_completion_tokens: int = 16384,
        min_pixels: Optional[int] = None,
        max_pixels: Optional[int] = None,
        batch_size: int = 0,
        max_concurrency: int = 100,
        http_timeout: int = 600,
        **kwargs,
    ):
        self.backend = backend
        self.model_path = model_path
        self.server_url = server_url
        self.use_hf = use_hf
        self.temperature = temperature
        self.top_p = top_p
        self.max_completion_tokens = max_completion_tokens
        self.min_pixels = min_pixels or 3136
        self.max_pixels = max_pixels or 11289600
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.http_timeout = http_timeout

        self._client = self._create_client()

    def _create_client(self) -> MinerUClient:
        if self.backend == "http-client":
            logger.info(f"Using HTTP client with server_url: {self.server_url}")
            return MinerUClient(
                backend="http-client",
                server_url=self.server_url,
                model_path=self.model_path,
                batch_size=self.batch_size,
                max_concurrency=self.max_concurrency,
                http_timeout=self.http_timeout,
            )

        if self.use_hf or self.backend == "transformers":
            return self._create_hf_client()
        elif self.backend in ["vllm-engine", "vllm-async-engine"]:
            return self._create_vllm_client()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _create_hf_client(self) -> MinerUClient:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as e:
            raise ImportError(
                f"Please install required packages for HuggingFace backend: {e}"
            )

        if not self.model_path:
            raise ValueError("model_path is required for HuggingFace backend")

        logger.info(f"Loading dots.ocr model from: {self.model_path}")

        from transformers import __version__ as transformers_version
        from packaging import version

        dtype_key = (
            "dtype"
            if version.parse(transformers_version) >= version.parse("4.56.0")
            else "torch_dtype"
        )

        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            attn_implementation="flash_attention_2",
            **{dtype_key: torch.bfloat16},
            device_map="auto",
            trust_remote_code=True,
        )
        processor = AutoProcessor.from_pretrained(
            self.model_path, trust_remote_code=True, use_fast=True
        )

        logger.info("dots.ocr model loaded successfully")

        return MinerUClient(
            backend="transformers",
            model=model,
            processor=processor,
            model_path=self.model_path,
            batch_size=self.batch_size,
        )

    def _create_vllm_client(self) -> MinerUClient:
        try:
            import vllm
        except ImportError as e:
            raise ImportError(f"Please install vllm for vLLM backend: {e}")

        if not self.model_path:
            raise ValueError("model_path is required for vLLM backend")

        logger.info(f"Loading dots.ocr model with vLLM from: {self.model_path}")

        vllm_llm = vllm.LLM(
            model=self.model_path,
            trust_remote_code=True,
            gpu_memory_utilization=0.9,
            max_model_len=8192,
        )

        backend_type = (
            "vllm-async-engine"
            if self.backend == "vllm-async-engine"
            else "vllm-engine"
        )

        logger.info("dots.ocr vLLM model loaded successfully")

        return MinerUClient(
            backend=backend_type,
            vllm_llm=vllm_llm,
            model_path=self.model_path,
            batch_size=self.batch_size,
            max_concurrency=self.max_concurrency,
        )

    def _get_prompt(self, prompt_mode: str = "prompt_layout_all_en") -> str:
        return dict_promptmode_to_prompt.get(
            prompt_mode, dict_promptmode_to_prompt["prompt_layout_all_en"]
        )

    def _parse_dots_output(
        self, response: str, prompt_mode: str, image, min_pixels: int, max_pixels: int
    ) -> List[dict]:
        cells, filtered = post_process_output(
            response,
            prompt_mode,
            image,
            image,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
        )

        if filtered or not isinstance(cells, list):
            logger.warning(
                f"Model output parsing failed or returned non-list: {type(cells)}"
            )
            return []

        return cells

    def _convert_to_content_blocks(
        self, cells: List[dict], page_idx: int, width: int, height: int
    ) -> List[ContentBlock]:
        blocks = []
        for cell in cells:
            category = cell.get("category", "Text")
            text = cell.get("text", "")
            bbox = cell.get("bbox", [0, 0, 0, 0])

            block_type = DOTS_TO_MINERU_TYPE.get(category, "text")

            block = ContentBlock(
                type=block_type,
                bbox=[
                    bbox[0] / width,
                    bbox[1] / height,
                    bbox[2] / width,
                    bbox[3] / height,
                ],
                content=text,
                angle=0,
            )

            blocks.append(block)

        return blocks

    def _process_outputs(
        self, images: List, outputs: List[str], prompt_mode: str
    ) -> List[List[ContentBlock]]:
        results = []
        for idx, (image, response) in enumerate(zip(images, outputs)):
            width, height = image.size

            try:
                cells = self._parse_dots_output(
                    response, prompt_mode, image, self.min_pixels, self.max_pixels
                )
                blocks = self._convert_to_content_blocks(cells, idx, width, height)
            except Exception as e:
                logger.warning(f"Error processing image {idx}: {e}")
                blocks = []

            results.append(blocks)

        return results

    def batch_two_step_extract(
        self,
        images: List,
        prompt_mode: str = "prompt_layout_all_en",
        not_extract_list: list = None,
    ) -> List[List[ContentBlock]]:
        total = len(images)
        logger.info(
            f"Processing {total} images with dots.ocr (prompt_mode: {prompt_mode})"
        )

        prompt = self._get_prompt(prompt_mode)
        sampling_params = MinerUSamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_completion_tokens,
        )

        start_time = time.time()
        outputs = self._client.batch_predict(
            images=images,
            prompts=[prompt] * len(images),
            sampling_params=[sampling_params] * len(images),
        )
        elapsed = time.time() - start_time
        logger.debug(
            f"Inference done in {elapsed:.2f}s, speed: {round(total / elapsed, 3)} page/s"
        )

        results = self._process_outputs(images, outputs, prompt_mode)
        return results

    async def aio_batch_two_step_extract(
        self,
        images: List,
        prompt_mode: str = "prompt_layout_all_en",
        not_extract_list: list = None,
    ) -> List[List[ContentBlock]]:
        total = len(images)
        logger.info(
            f"Processing {total} images with dots.ocr async (prompt_mode: {prompt_mode})"
        )

        prompt = self._get_prompt(prompt_mode)
        sampling_params = MinerUSamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_completion_tokens,
        )

        start_time = time.time()
        outputs = await self._client.aio_batch_predict(
            images=images,
            prompts=[prompt] * len(images),
            sampling_params=[sampling_params] * len(images),
        )
        elapsed = time.time() - start_time
        logger.debug(
            f"Inference done in {elapsed:.2f}s, speed: {round(total / elapsed, 3)} page/s"
        )

        results = self._process_outputs(images, outputs, prompt_mode)
        return results


def create_dots_ocr_client(
    backend: str = "transformers",
    model_path: Optional[str] = None,
    server_url: Optional[str] = None,
    **kwargs,
) -> DotsOCRClient:
    return DotsOCRClient(
        backend=backend, model_path=model_path, server_url=server_url, **kwargs
    )
