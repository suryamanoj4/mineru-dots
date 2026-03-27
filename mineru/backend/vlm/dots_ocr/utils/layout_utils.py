import json
import re
from PIL import Image
from typing import Dict, List, Optional, Tuple


def post_process_output(
    response: str,
    prompt_mode: str,
    origin_image: Image.Image,
    input_image: Image.Image,
    min_pixels: Optional[int] = None,
    max_pixels: Optional[int] = None,
) -> Tuple[List[Dict], bool]:
    """Post-process model output to extract layout elements."""
    if prompt_mode in [
        "prompt_ocr",
        "prompt_table_html",
        "prompt_table_latex",
        "prompt_formula_latex",
    ]:
        return response, False

    json_load_failed = False
    cells = response

    try:
        if isinstance(cells, str):
            cells = json.loads(cells)

        cells = post_process_cells(
            origin_image,
            cells,
            input_image.width,
            input_image.height,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
        )
        return cells, False
    except Exception:
        json_load_failed = True

    if json_load_failed:
        cleaner = OutputCleaner()
        response_clean = cleaner.clean_model_output(cells)
        if isinstance(response_clean, list):
            response_clean = "\n\n".join(
                [cell.get("text", "") for cell in response_clean if "text" in cell]
            )
        return response_clean, True

    return [], True


def post_process_cells(
    origin_image: Image.Image,
    cells: List[Dict],
    input_width: int,
    input_height: int,
    factor: int = 28,
    min_pixels: int = 3136,
    max_pixels: int = 11289600,
) -> List[Dict]:
    """Post-process cell bounding boxes, converting coordinates from resized to original dimensions."""
    from .image_utils import smart_resize

    if not cells:
        return cells

    original_width, original_height = origin_image.size
    input_height, input_width = smart_resize(
        input_height, input_width, min_pixels=min_pixels, max_pixels=max_pixels
    )

    scale_x = input_width / original_width
    scale_y = input_height / original_height

    cells_out = []
    for cell in cells:
        if "bbox" not in cell:
            continue
        bbox = cell["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        bbox_resized = [
            int(float(bbox[0]) / scale_x),
            int(float(bbox[1]) / scale_y),
            int(float(bbox[2]) / scale_x),
            int(float(bbox[3]) / scale_y),
        ]
        cell_copy = cell.copy()
        cell_copy["bbox"] = bbox_resized
        cells_out.append(cell_copy)

    return cells_out


def is_legal_bbox(cells: List[Dict]) -> bool:
    """Check if all bounding boxes are valid."""
    for cell in cells:
        bbox = cell.get("bbox", [])
        if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return False
    return True


class OutputCleaner:
    """Data Cleaner - Simplified version for cleaning model output"""

    def __init__(self):
        self.dict_pattern = re.compile(
            r'\{[^{}]*?"bbox"\s*:\s*\[[^\]]*?\][^{}]*?\}', re.DOTALL
        )
        self.bbox_pattern = re.compile(r'"bbox"\s*:\s*\[([^\]]+)\]')

    def clean_model_output(self, response):
        """Clean model output and try to extract valid JSON."""
        if isinstance(response, list):
            return self._clean_list_data(response)

        if isinstance(response, str):
            return self._clean_string_data(response)

        return response, True

    def _clean_list_data(self, data: List[Dict]) -> List[Dict]:
        """Clean list-type data."""
        cleaned_data = []

        for item in data:
            if not isinstance(item, dict):
                continue

            if "bbox" in item:
                bbox = item["bbox"]
                if isinstance(bbox, list) and len(bbox) == 3:
                    continue

            cleaned_item = {}
            if "category" in item:
                cleaned_item["category"] = item["category"]
            if "text" in item:
                cleaned_item["text"] = item["text"]
            if "bbox" in item:
                cleaned_item["bbox"] = item["bbox"]

            if cleaned_item:
                cleaned_data.append(cleaned_item)

        return cleaned_data

    def _clean_string_data(self, response: str) -> str:
        """Clean string-type data."""
        try:
            matches = self.dict_pattern.findall(response)
            if matches:
                parsed = []
                for match in matches:
                    try:
                        item = json.loads(match)
                        parsed.append(item)
                    except Exception:
                        continue
                if parsed:
                    return self._clean_list_data(parsed)
        except Exception:
            pass

        return response
