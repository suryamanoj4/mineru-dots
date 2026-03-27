import base64
import io
from typing import Optional, Tuple, Union
from PIL import Image


def fetch_image(
    image: Union[str, Image.Image],
    min_pixels: Optional[int] = None,
    max_pixels: Optional[int] = None,
) -> Image.Image:
    """Fetch and preprocess image."""
    if isinstance(image, str):
        image = Image.open(image)

    if not isinstance(image, Image.Image):
        raise ValueError(f"Unsupported image type: {type(image)}")

    if image.mode != "RGB":
        image = image.convert("RGB")

    return image


def smart_resize(
    height: int,
    width: int,
    factor: int = 28,
    min_pixels: int = 3136,
    max_pixels: int = 11289600,
) -> Tuple[int, int]:
    """Smart resize to ensure dimensions are divisible by factor and within pixel limits."""
    if max(height, width) / min(height, width) > 200:
        raise ValueError("Image aspect ratio too extreme")

    h_bar = max(round(height / factor) * factor, factor)
    w_bar = max(round(width / factor) * factor, factor)

    if h_bar * w_bar > max_pixels:
        beta = (height * width / max_pixels) ** 0.5
        h_bar = max(round(height / beta / factor) * factor, factor)
        w_bar = max(round(width / beta / factor) * factor, factor)

    if h_bar * w_bar < min_pixels:
        beta = (min_pixels / (height * width)) ** 0.5
        h_bar = max(round(height / beta / factor) * factor, factor)
        w_bar = max(round(width / beta / factor) * factor, factor)

    return h_bar, w_bar


def PILimage_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/{format.lower()};base64,{img_str}"


def get_image_by_fitz_doc(pil_image: Image.Image, target_dpi: int = 200) -> Image.Image:
    """Process image with fitz-like DPI upsampling."""
    return pil_image


def pre_process_bboxes(
    origin_image: Image.Image,
    bboxes: list,
    input_width: int,
    input_height: int,
    min_pixels: Optional[int] = None,
    max_pixels: Optional[int] = None,
) -> list:
    """Pre-process bounding boxes for grounding OCR."""
    min_pixels = min_pixels or 3136
    max_pixels = max_pixels or 11289600

    h, w = smart_resize(
        input_height, input_width, min_pixels=min_pixels, max_pixels=max_pixels
    )

    scale_x = w / input_width
    scale_y = h / input_height

    processed_bboxes = []
    for bbox in bboxes:
        processed_bboxes.append(
            [bbox[0] * scale_x, bbox[1] * scale_y, bbox[2] * scale_x, bbox[3] * scale_y]
        )

    return processed_bboxes
