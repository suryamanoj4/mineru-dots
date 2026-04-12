# Copyright (c) Opendatalab. All rights reserved.
from __future__ import annotations

import shutil
from typing import Iterable

import numpy as np
from PIL import Image


class TesseractOCRModel:
    LANG_ALIASES = {
        "ch": "chi_sim",
        "ch_server": "chi_sim",
        "ch_lite": "chi_sim",
        "en": "eng",
        "korean": "kor",
        "japan": "jpn",
        "chinese_cht": "chi_tra",
        "ta": "tam",
        "te": "tel",
        "ka": "kan",
        "th": "tha",
        "el": "ell",
        "latin": "eng",
        "arabic": "ara",
        "east_slavic": "rus",
        "cyrillic": "rus",
        "devanagari": "hin",
    }

    def __init__(
        self,
        lang: str = "eng",
        oem: int = 3,
        psm: int = 3,
        config: str = "",
        tesseract_cmd: str | None = None,
        tessdata_dir: str | None = None,
        min_confidence: float = 0.0,
    ):
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise ImportError(
                "Please install pytesseract to use the Tesseract OCR backend."
            ) from exc

        self.tesseract = pytesseract
        self.Output = Output
        self.lang = self.LANG_ALIASES.get(lang, lang or "eng")
        self.oem = oem
        self.psm = psm
        self.extra_config = config.strip()
        self.tessdata_dir = tessdata_dir
        self.min_confidence = min_confidence

        if tesseract_cmd:
            self.tesseract.pytesseract.tesseract_cmd = tesseract_cmd
            binary = tesseract_cmd
        else:
            binary = shutil.which("tesseract") or self.tesseract.pytesseract.tesseract_cmd

        if not binary:
            raise RuntimeError(
                "Tesseract binary was not found. Install `tesseract` or provide "
                "`tesseract_cmd`."
            )

        self.tesseract_cmd = binary

    def predict(self, img: np.ndarray) -> list[dict]:
        data = self._image_to_data(img)
        return list(self._iter_segments(data))

    def get_structured_data(self, img: np.ndarray) -> list[dict]:
        """Return structured OCR results (blocks -> paragraphs -> lines -> words)."""
        data = self._image_to_data(img)
        total = len(data.get("text", []))
        
        blocks = {}
        for idx in range(total):
            level = data["level"][idx]
            block_num = data["block_num"][idx]
            par_num = data["par_num"][idx]
            line_num = data["line_num"][idx]
            word_num = data["word_num"][idx]
            
            text = (data["text"][idx] or "").strip()
            confidence = self._normalize_confidence(data["conf"][idx])
            
            left = int(data["left"][idx])
            top = int(data["top"][idx])
            width = int(data["width"][idx])
            height = int(data["height"][idx])
            
            if width <= 0 or height <= 0:
                continue
                
            bbox = [left, top, left + width, top + height]
            
            if block_num not in blocks:
                blocks[block_num] = {"paragraphs": {}, "bbox": bbox}
            
            # Update block bbox to encompass all its elements
            b = blocks[block_num]
            b["bbox"] = [
                min(b["bbox"][0], bbox[0]),
                min(b["bbox"][1], bbox[1]),
                max(b["bbox"][2], bbox[2]),
                max(b["bbox"][3], bbox[3])
            ]
            
            if par_num not in b["paragraphs"]:
                b["paragraphs"][par_num] = {"lines": {}, "bbox": bbox}
            
            p = b["paragraphs"][par_num]
            p["bbox"] = [
                min(p["bbox"][0], bbox[0]),
                min(p["bbox"][1], bbox[1]),
                max(p["bbox"][2], bbox[2]),
                max(p["bbox"][3], bbox[3])
            ]
            
            if line_num not in p["lines"]:
                p["lines"][line_num] = {"words": [], "bbox": bbox}
            
            l = p["lines"][line_num]
            l["bbox"] = [
                min(l["bbox"][0], bbox[0]),
                min(l["bbox"][1], bbox[1]),
                max(l["bbox"][2], bbox[2]),
                max(l["bbox"][3], bbox[3])
            ]
            
            if level == 5:  # Word level
                if not text:
                    continue
                if confidence < self.min_confidence:
                    continue
                l["words"].append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox
                })

        # Convert nested dicts to sorted lists
        structured_blocks = []
        for b_num in sorted(blocks.keys()):
            b = blocks[b_num]
            structured_paragraphs = []
            for p_num in sorted(b["paragraphs"].keys()):
                p = b["paragraphs"][p_num]
                structured_lines = []
                for l_num in sorted(p["lines"].keys()):
                    l = p["lines"][l_num]
                    if l["words"]:
                        structured_lines.append({
                            "words": l["words"],
                            "bbox": l["bbox"]
                        })
                if structured_lines:
                    structured_paragraphs.append({
                        "lines": structured_lines,
                        "bbox": p["bbox"]
                    })
            if structured_paragraphs:
                structured_blocks.append({
                    "paragraphs": structured_paragraphs,
                    "bbox": b["bbox"]
                })
        
        return structured_blocks

    def ocr(
        self,
        img,
        det: bool = True,
        rec: bool = True,
        mfd_res=None,
        tqdm_enable: bool = False,
        tqdm_desc: str = "OCR-rec Predict",
    ):
        del mfd_res, tqdm_enable, tqdm_desc

        if isinstance(img, list) and det:
            raise ValueError("When input is a list of images, det must be false.")

        imgs = img if isinstance(img, list) else [img]

        if det and rec:
            results = []
            for single_img in imgs:
                data = self._image_to_data(single_img)
                results.append(self._format_output(data, include_recognition=True))
            return results

        if det and not rec:
            results = []
            for single_img in imgs:
                data = self._image_to_data(single_img)
                boxes = self._format_output(data, include_recognition=False)
                results.append(boxes)
            return results

        if not det and rec:
            rec_results = []
            for single_img in imgs:
                rec_results.append(self._recognize_crop(single_img))
            return [rec_results]

        raise ValueError("At least one of `det` or `rec` must be enabled.")

    def __call__(self, img, mfd_res=None):
        del mfd_res
        words = list(self._iter_segments(self._image_to_data(img)))
        if not words:
            return None, None
        line_results = self._merge_words_to_lines(words, include_recognition=True)
        dt_boxes = [item[0] for item in line_results]
        rec_res = [item[1] for item in line_results]
        return dt_boxes, rec_res

    def _image_to_data(self, img) -> dict:
        pil_img = self._to_pil_image(img)
        return self.tesseract.image_to_data(
            pil_img,
            lang=self.lang,
            config=self._build_config(),
            output_type=self.Output.DICT,
        )

    def _recognize_crop(self, img) -> tuple[str, float]:
        data = self._image_to_data(img)
        segments = self._iter_segments(data)

        texts = []
        confidences = []
        for segment in segments:
            texts.append(segment["text"])
            confidences.append(segment["confidence"])

        if not texts:
            return "", 0.0

        text = " ".join(texts).strip()
        confidence = round(sum(confidences) / len(confidences), 3)
        return text, confidence

    def _format_output(
        self,
        data: dict,
        include_recognition: bool = True,
    ) -> list:
        words = list(self._iter_segments(data))
        return self._merge_words_to_lines(words, include_recognition=include_recognition)

    def _iter_segments(self, data: dict) -> Iterable[dict]:
        """Yield word-level segments from Tesseract output.

        Words are later merged into lines using _merge_words_to_lines()
        to match PaddleOCR's geometric merging behavior.
        """
        total = len(data.get("text", []))
        for idx in range(total):
            if data["level"][idx] != 5:  # Level 5 is word
                continue

            text = (data["text"][idx] or "").strip()
            if not text:
                continue

            confidence = self._normalize_confidence(data["conf"][idx])
            if confidence < self.min_confidence:
                continue

            left = int(data["left"][idx])
            top = int(data["top"][idx])
            width = int(data["width"][idx])
            height = int(data["height"][idx])

            if width <= 0 or height <= 0:
                continue

            box = [
                [left, top],
                [left + width, top],
                [left + width, top + height],
                [left, top + height],
            ]
            yield {
                "text": text,
                "confidence": confidence,
                "box": box,
                "bbox": [left, top, left + width, top + height],
            }

    @staticmethod
    def _is_overlaps_y(bbox1: list, bbox2: list, overlap_ratio: float = 0.8) -> bool:
        """Check if two bboxes overlap significantly on the Y axis.

        Matches the logic in mineru/utils/ocr_utils.py::_is_overlaps_y_exceeds_threshold
        used by PaddleOCR's merge_spans_to_line.
        """
        _, y0_1, _, y1_1 = bbox1
        _, y0_2, _, y1_2 = bbox2

        overlap = max(0, min(y1_1, y1_2) - max(y0_1, y0_2))
        height1, height2 = y1_1 - y0_1, y1_2 - y0_2
        min_height = min(height1, height2)

        return (overlap / min_height) > overlap_ratio if min_height > 0 else False

    def _merge_words_to_lines(self, words: list[dict], include_recognition: bool = False) -> list:
        """Merge word-level results into line-level results using Y-coordinate proximity.

        This matches PaddleOCR's merge_spans_to_line behavior so that downstream
        pipeline stages receive structurally equivalent output regardless of OCR engine.

        Args:
            words: List of word dicts with 'text', 'confidence', 'box', 'bbox' keys.
            include_recognition: If True, returns [[box, (text, score)], ...] format.
                               If False, returns [box, ...] format (detection only).

        Returns:
            List of line-level results in the requested format.
        """
        if not words:
            return []

        # Sort by Y position (top coordinate)
        words.sort(key=lambda w: (w["bbox"][1], w["bbox"][0]))

        # Group words into lines based on Y-axis overlap
        lines = []
        current_line = [words[0]]

        for word in words[1:]:
            if self._is_overlaps_y(word["bbox"], current_line[-1]["bbox"]):
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]

        if current_line:
            lines.append(current_line)

        # Merge each line into a single result
        results = []
        for line_words in lines:
            # Compute encompassing bbox
            all_lefts = [w["bbox"][0] for w in line_words]
            all_tops = [w["bbox"][1] for w in line_words]
            all_rights = [w["bbox"][2] for w in line_words]
            all_bottoms = [w["bbox"][3] for w in line_words]

            min_left = min(all_lefts)
            min_top = min(all_tops)
            max_right = max(all_rights)
            max_bottom = max(all_bottoms)

            line_box = [
                [min_left, min_top],
                [max_right, min_top],
                [max_right, max_bottom],
                [min_left, max_bottom],
            ]

            # Sort words in line by X position for correct reading order
            line_words.sort(key=lambda w: w["bbox"][0])
            line_text = " ".join(w["text"] for w in line_words)
            line_conf = sum(w["confidence"] for w in line_words) / len(line_words)

            if include_recognition:
                results.append([line_box, (line_text, round(line_conf, 3))])
            else:
                results.append(line_box)

        return results

    def _build_config(self) -> str:
        parts = [f"--oem {self.oem}", f"--psm {self.psm}"]
        if self.tessdata_dir:
            parts.append(f'--tessdata-dir "{self.tessdata_dir}"')
        if self.extra_config:
            parts.append(self.extra_config)
        return " ".join(parts)

    @staticmethod
    def _normalize_confidence(value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        if confidence < 0:
            return 0.0
        return round(confidence / 100.0, 3)

    @staticmethod
    def _to_pil_image(img) -> Image.Image:
        if isinstance(img, Image.Image):
            if img.mode not in ("RGB", "L"):
                return img.convert("RGB")
            return img

        if not isinstance(img, np.ndarray):
            raise TypeError(
                f"Unsupported image type for Tesseract OCR: {type(img)!r}"
            )

        if img.ndim == 2:
            return Image.fromarray(img)

        if img.ndim != 3:
            raise ValueError(f"Unsupported image shape for Tesseract OCR: {img.shape}")

        if img.shape[2] == 3:
            rgb_img = img[:, :, ::-1]
            return Image.fromarray(rgb_img)

        if img.shape[2] == 4:
            rgba_img = img[:, :, [2, 1, 0, 3]]
            return Image.fromarray(rgba_img, mode="RGBA").convert("RGB")

        raise ValueError(f"Unsupported image shape for Tesseract OCR: {img.shape}")
