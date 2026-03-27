import os
import requests
from typing import Optional
from PIL import Image

from ..utils.image_utils import PILimage_to_base64


def inference_with_vllm(
    image: Image.Image,
    prompt: str,
    protocol: str = "http",
    ip: str = "localhost",
    port: int = 8000,
    temperature: float = 0.1,
    top_p: float = 0.9,
    max_completion_tokens: int = 32768,
    model_name: str = "model",
    system_prompt: Optional[str] = None,
):
    """Inference with vLLM server."""
    from openai import OpenAI

    addr = f"{protocol}://{ip}:{port}/v1"
    client = OpenAI(api_key=os.environ.get("API_KEY", "0"), base_url=addr)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": PILimage_to_base64(image)},
                },
                {"type": "text", "text": f"<|img|><|imgpad|><|endofimg|>{prompt}"},
            ],
        }
    )

    try:
        response = client.chat.completions.create(
            messages=messages,
            model=model_name,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
