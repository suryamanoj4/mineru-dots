import time
from typing import List, Optional

from loguru import logger

from .dots_ocr.utils.layout_utils import post_process_output
from .dots_ocr.utils.prompts import dict_promptmode_to_prompt
from .utils import set_default_gpu_memory_utilization
from vparse.utils.compat import get_env_with_legacy
from mineru_vl_utils import MinerUClient as VParseClient
from mineru_vl_utils import MinerUSamplingParams as VParseSamplingParams
from mineru_vl_utils.structs import ContentBlock


DOTS_TO_VPARSE_TYPE = {
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
        max_completion_tokens: int = 32768,
        min_pixels: Optional[int] = None,
        max_pixels: Optional[int] = None,
        batch_size: int = 0,
        max_concurrency: int = 100,
        http_timeout: int = 600,
        gpu_memory_utilization: Optional[float] = None,
        max_model_len: Optional[int] = None,
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
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len

        self._client = self._create_client()

    def _create_client(self) -> VParseClient:
        if self.backend == "http-client":
            logger.info(f"Using HTTP client with server_url: {self.server_url}")
            return VParseClient(
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

    def _create_hf_client(self) -> VParseClient:
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

        return VParseClient(
            backend="transformers",
            model=model,
            processor=processor,
            model_path=self.model_path,
            batch_size=self.batch_size,
        )

    def _create_vllm_client(self) -> VParseClient:
        try:
            import vllm
        except ImportError as e:
            raise ImportError(f"Please install vllm for vLLM backend: {e}")

        if not self.model_path:
            raise ValueError("model_path is required for vLLM backend")

        logger.info(f"Loading dots.ocr model with vLLM from: {self.model_path}")

        if self.gpu_memory_utilization is None:
            env_val = get_env_with_legacy("VPARSE_GPU_MEMORY_UTILIZATION", "MINERU_GPU_MEMORY_UTILIZATION")
            if env_val is not None:
                try:
                    self.gpu_memory_utilization = float(env_val)
                except ValueError:
                    logger.warning(f"Invalid VPARSE_GPU_MEMORY_UTILIZATION: {env_val}, using default")
                    self.gpu_memory_utilization = set_default_gpu_memory_utilization()
            else:
                self.gpu_memory_utilization = set_default_gpu_memory_utilization()

        if self.max_model_len is None:
            env_val = get_env_with_legacy("VPARSE_MAX_MODEL_LEN", "MINERU_MAX_MODEL_LEN")
            if env_val is not None:
                try:
                    self.max_model_len = int(env_val)
                except ValueError:
                    logger.warning(f"Invalid VPARSE_MAX_MODEL_LEN: {env_val}, using default 32768")
                    self.max_model_len = 32768
            else:
                self.max_model_len = 32768

        logger.info(f"Using GPU memory utilization: {self.gpu_memory_utilization}")
        logger.info(f"Using max_model_len: {self.max_model_len}")

        vllm_llm = vllm.LLM(
            model=self.model_path,
            trust_remote_code=True,
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.max_model_len,
        )

        backend_type = (
            "vllm-async-engine"
            if self.backend == "vllm-async-engine"
            else "vllm-engine"
        )

        logger.info("dots.ocr vLLM model loaded successfully")

        # Create VParseClient - prompts are passed directly in batch_two_step_extract
        vparse_client = VParseClient(
            backend=backend_type,
            vllm_llm=vllm_llm,
            model_path=self.model_path,
            batch_size=self.batch_size,
            max_concurrency=self.max_concurrency,
        )
        
        # Patch the internal VLLM client's build_messages method for dots.ocr compatibility
        # dots.ocr's chat template expects string content, not OpenAI list format
        def build_messages_string(prompt: str, _num_images: int) -> list[dict]:
            prompt = prompt or vparse_client.client.prompt
            messages = []
            if vparse_client.client.system_prompt:
                messages.append({"role": "system", "content": vparse_client.client.system_prompt})
            # Use string content format for chat template compatibility
            # Image is passed separately via multi_modal_data in vLLM
            user_content = prompt if prompt else ""
            messages.append({"role": "user", "content": user_content})
            return messages
        
        vparse_client.client.build_messages = build_messages_string
        
        return vparse_client

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

            block_type = DOTS_TO_VPARSE_TYPE.get(category, "text")

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

        # Get the dots.ocr prompt and add special tokens required by the model
        base_prompt = self._get_prompt(prompt_mode)
        # dots.ocr requires special tokens before the prompt text
        prompt = f"<|img|><|imgpad|><|endofimg|>{base_prompt}"
        
        sampling_params = VParseSamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_completion_tokens,
        )

        start_time = time.time()
        # Access internal client's batch_predict for raw text output
        # dots.ocr returns JSON with both layout and content in one pass
        # Pass prompt as a list to avoid chat template issues
        outputs = self._client.client.batch_predict(
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

        # Get the dots.ocr prompt and add special tokens required by the model
        base_prompt = self._get_prompt(prompt_mode)
        # dots.ocr requires special tokens before the prompt text
        prompt = f"<|img|><|imgpad|><|endofimg|>{base_prompt}"
        
        sampling_params = VParseSamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_completion_tokens,
        )

        start_time = time.time()
        # Access internal client's aio_batch_predict for raw text output
        # Pass prompt as a list to avoid chat template issues
        outputs = await self._client.client.aio_batch_predict(
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
