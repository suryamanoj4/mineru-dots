import time
from typing import List, Optional
from PIL import Image

from loguru import logger


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
        num_thread: int = 16,
        dpi: int = 200,
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
        self.num_thread = num_thread
        self.dpi = dpi
        self.min_pixels = min_pixels
        self.max_pixels = max_pixels
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.http_timeout = http_timeout

        self._model = None
        self._processor = None
        self._init_model()

    def _init_model(self):
        if self.backend == "http-client":
            logger.info(f"Using HTTP client with server_url: {self.server_url}")
            return

        if self.use_hf or self.backend == "transformers":
            self._load_hf_model()
        elif self.backend in ["vllm-engine", "vllm-async-engine"]:
            self._load_vllm_model()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _load_hf_model(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
            from qwen_vl_utils import process_vision_info
        except ImportError as e:
            raise ImportError(
                f"Please install required packages for HuggingFace backend: {e}"
            )

        if not self.model_path:
            raise ValueError("model_path is required for HuggingFace backend")

        logger.info(f"Loading dots.ocr model from: {self.model_path}")
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            attn_implementation="flash_attention_2",
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        self._processor = AutoProcessor.from_pretrained(
            self.model_path, trust_remote_code=True, use_fast=True
        )
        self._process_vision_info = process_vision_info
        logger.info("dots.ocr model loaded successfully")

    def _load_vllm_model(self):
        try:
            import vllm
        except ImportError as e:
            raise ImportError(f"Please install vllm for vLLM backend: {e}")

        if not self.model_path:
            raise ValueError("model_path is required for vLLM backend")

        logger.info(f"Loading dots.ocr model with vLLM from: {self.model_path}")
        self._vllm_llm = vllm.LLM(
            model=self.model_path,
            trust_remote_code=True,
            gpu_memory_utilization=0.9,
        )
        logger.info("dots.ocr vLLM model loaded successfully")

    def _get_prompt(self, prompt_mode: str = "prompt_layout_all_en") -> str:
        from .dots_ocr.utils.prompts import dict_promptmode_to_prompt

        return dict_promptmode_to_prompt.get(
            prompt_mode, dict_promptmode_to_prompt["prompt_layout_all_en"]
        )

    def _inference_single_image(
        self, image: Image.Image, prompt_mode: str = "prompt_layout_all_en"
    ) -> List[dict]:
        from .dots_ocr.utils.image_utils import fetch_image, smart_resize
        from .dots_ocr.utils.layout_utils import post_process_output

        prompt = self._get_prompt(prompt_mode)

        min_pixels = self.min_pixels or 3136
        max_pixels = self.max_pixels or 11289600

        image = fetch_image(image, min_pixels=min_pixels, max_pixels=max_pixels)
        input_height, input_width = smart_resize(image.height, image.width)

        if self.backend == "http-client":
            response = self._inference_http(image, prompt)
        elif self.use_hf or self.backend == "transformers":
            response = self._inference_hf(image, prompt)
        elif self.backend in ["vllm-engine", "vllm-async-engine"]:
            response = self._inference_vllm(image, prompt)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

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

    def _inference_http(self, image: Image.Image, prompt: str) -> str:
        from .dots_ocr.model.inference import inference_with_vllm

        if not self.server_url:
            raise ValueError("server_url is required for HTTP client")

        protocol, addr = (
            self.server_url.split("://")
            if "://" in self.server_url
            else ("http", self.server_url)
        )
        ip, port = addr.rsplit(":", 1) if ":" in addr else (addr, "8000")

        response = inference_with_vllm(
            image,
            prompt,
            model_name="model",
            protocol=protocol,
            ip=ip,
            port=int(port),
            temperature=self.temperature,
            top_p=self.top_p,
            max_completion_tokens=self.max_completion_tokens,
        )
        return response

    def _inference_hf(self, image: Image.Image, prompt: str) -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = self._process_vision_info(messages)
        inputs = self._processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )

        inputs = inputs.to("cuda")

        generated_ids = self._model.generate(**inputs, max_new_tokens=24000)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        response = self._processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return response

    def _inference_vllm(self, image: Image.Image, prompt: str) -> str:
        from vllm import SamplingParams
        from .dots_ocr.utils.image_utils import fetch_image

        if not hasattr(self, "_vllm_llm"):
            raise ValueError("vLLM model not loaded")

        min_pixels = self.min_pixels or 3136
        max_pixels = self.max_pixels or 11289600

        image = fetch_image(image, min_pixels=min_pixels, max_pixels=max_pixels)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        prompt_with_img = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        sampling_params = SamplingParams(
            max_tokens=self.max_completion_tokens or 24000,
            temperature=self.temperature or 0.1,
            top_p=self.top_p or 0.9,
        )

        outputs = self._vllm_llm.generate(
            prompt=prompt_with_img,
            image_data=[image],
            sampling_params=sampling_params,
        )

        return outputs[0].outputs[0].text

    def _convert_to_mineru_format(
        self, cells: List[dict], page_idx: int, width: int, height: int
    ) -> List[dict]:
        blocks = []
        for cell in cells:
            category = cell.get("category", "Text")
            text = cell.get("text", "")
            bbox = cell.get("bbox", [0, 0, 0, 0])

            block_type = DOTS_TO_MINERU_TYPE.get(category, "text")

            block = {
                "type": block_type,
                "bbox": [
                    bbox[0] / width,
                    bbox[1] / height,
                    bbox[2] / width,
                    bbox[3] / height,
                ],
                "content": text,
                "angle": 0,
            }

            if block_type == "table":
                block["content"] = text

            blocks.append(block)

        return blocks

    def batch_two_step_extract(
        self,
        images: List[Image.Image],
        prompt_mode: str = "prompt_layout_all_en",
        not_extract_list: list = None,
    ) -> List[List[dict]]:
        results = []
        total = len(images)

        logger.info(
            f"Processing {total} images with dots.ocr (prompt_mode: {prompt_mode})"
        )

        for idx, image in enumerate(images):
            start_time = time.time()
            width, height = image.size

            try:
                cells = self._inference_single_image(image, prompt_mode)
                blocks = self._convert_to_mineru_format(cells, idx, width, height)
            except Exception as e:
                logger.warning(f"Error processing image {idx}: {e}")
                blocks = []

            results.append(blocks)
            elapsed = time.time() - start_time
            logger.debug(f"Page {idx + 1}/{total} done in {elapsed:.2f}s")

        return results

    async def aio_batch_two_step_extract(
        self,
        images: List[Image.Image],
        prompt_mode: str = "prompt_layout_all_en",
        not_extract_list: list = None,
    ) -> List[List[dict]]:
        return self.batch_two_step_extract(images, prompt_mode, not_extract_list)


def create_dots_ocr_client(
    backend: str = "transformers",
    model_path: Optional[str] = None,
    server_url: Optional[str] = None,
    **kwargs,
) -> DotsOCRClient:
    return DotsOCRClient(
        backend=backend, model_path=model_path, server_url=server_url, **kwargs
    )
