from io import BytesIO
from unittest import mock

import pytest
from PIL import Image

from vparse.integrations.tesseract_scan import scan_prescription_image


def _build_image_bytes() -> bytes:
    image = Image.new("RGB", (32, 16), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_scan_prescription_image_returns_normalized_lines():
    image_bytes = _build_image_bytes()

    with mock.patch(
        "vparse.integrations.tesseract_scan.TesseractOCRModel"
    ) as mock_tesseract:
        mock_instance = mock_tesseract.return_value
        mock_instance.lang = "eng"
        mock_instance.get_structured_data.return_value = [
            {
                "paragraphs": [
                    {
                        "lines": [
                            {
                                "bbox": [1, 2, 3, 4],
                                "words": [
                                    {"text": "Tab", "confidence": 0.8, "bbox": [1, 2, 2, 4]},
                                    {"text": "Rabicet-20", "confidence": 0.6, "bbox": [2, 2, 3, 4]},
                                ],
                            }
                        ]
                    }
                ]
            }
        ]

        result = scan_prescription_image(
            image_bytes,
            filename="rx.png",
            content_type="image/png",
        )

    assert result["meta"]["engine"] == "tesseract"
    assert result["meta"]["image_width"] == 32
    assert result["lines"] == [
        {
            "text": "Tab Rabicet-20",
            "confidence": 0.7,
            "bbox": [1, 2, 3, 4],
            "words": [
                {"text": "Tab", "confidence": 0.8, "bbox": [1, 2, 2, 4]},
                {"text": "Rabicet-20", "confidence": 0.6, "bbox": [2, 2, 3, 4]},
            ],
        }
    ]


def test_scan_prescription_image_rejects_unsupported_content_type():
    with pytest.raises(ValueError, match="Unsupported image content type"):
        scan_prescription_image(b"abc", filename="rx.gif", content_type="image/gif")


def test_scan_prescription_image_rejects_invalid_image_payload():
    with pytest.raises(ValueError, match="Invalid image payload"):
        scan_prescription_image(b"not-an-image", filename="rx.png", content_type="image/png")
