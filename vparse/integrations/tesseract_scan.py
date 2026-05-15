from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from vparse.model.ocr.tesseract import TesseractOCRModel

_SUPPORTED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
}
_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _validate_image_source(
    *, filename: str | None = None, content_type: str | None = None
) -> None:
    if content_type and content_type.lower() not in _SUPPORTED_CONTENT_TYPES:
        raise ValueError(
            "Unsupported image content type. Supported types: image/jpeg, image/png."
        )

    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix and suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError("Unsupported image file extension. Supported: .jpg, .jpeg, .png.")


def _flatten_structured_data(structured_data: list[dict]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []

    for block in structured_data:
        for paragraph in block.get("paragraphs", []):
            for line in paragraph.get("lines", []):
                words = []
                word_confidences = []
                for word in line.get("words", []):
                    text = str(word.get("text", "")).strip()
                    if not text:
                        continue
                    confidence = float(word.get("confidence", 0.0))
                    bbox = word.get("bbox")
                    word_confidences.append(confidence)
                    words.append(
                        {
                            "text": text,
                            "confidence": confidence,
                            "bbox": bbox,
                        }
                    )

                if not words:
                    continue

                line_text = " ".join(word["text"] for word in words)
                avg_confidence = sum(word_confidences) / len(word_confidences)
                lines.append(
                    {
                        "text": line_text,
                        "confidence": round(avg_confidence, 4),
                        "bbox": line.get("bbox"),
                        "words": words,
                    }
                )

    return lines


def scan_prescription_image(
    image_bytes: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    lang: str = "eng",
    oem: int = 3,
    psm: int = 3,
    config: str = "",
    tesseract_cmd: str | None = None,
    tessdata_dir: str | None = None,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Run Tesseract OCR on a single prescription image.

    This is the intended import surface for external applications that want
    image-based OCR without going through the CLI or PDF-focused lite backend.
    """

    if not image_bytes:
        raise ValueError("Image payload is empty.")

    _validate_image_source(filename=filename, content_type=content_type)

    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError, ModuleNotFoundError) as exc:
        raise ValueError("Invalid image payload. Unable to decode image bytes.") from exc

    if image.mode != "RGB":
        image = image.convert("RGB")

    ocr_model = TesseractOCRModel(
        lang=lang,
        oem=oem,
        psm=psm,
        config=config,
        tesseract_cmd=tesseract_cmd,
        tessdata_dir=tessdata_dir,
        min_confidence=min_confidence,
    )
    structured_data = ocr_model.get_structured_data(image)
    lines = _flatten_structured_data(structured_data)

    return {
        "lines": lines,
        "meta": {
            "engine": "tesseract",
            "lang": ocr_model.lang,
            "image_width": image.width,
            "image_height": image.height,
            "filename": filename,
            "content_type": content_type,
        },
    }
