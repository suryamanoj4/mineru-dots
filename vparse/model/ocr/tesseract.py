# Copyright (c) Opendatalab. All rights reserved.
from __future__ import annotations

import shutil

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
        data = self._image_to_data(img)
        total = len(data.get("text", []))

        blocks = {}
        for idx in range(total):
            level = data["level"][idx]
            block_num = data["block_num"][idx]
            par_num = data["par_num"][idx]
            line_num = data["line_num"][idx]

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

            block = blocks[block_num]
            block["bbox"] = [
                min(block["bbox"][0], bbox[0]),
                min(block["bbox"][1], bbox[1]),
                max(block["bbox"][2], bbox[2]),
                max(block["bbox"][3], bbox[3]),
            ]

            if par_num not in block["paragraphs"]:
                block["paragraphs"][par_num] = {"lines": {}, "bbox": bbox}

            paragraph = block["paragraphs"][par_num]
            paragraph["bbox"] = [
                min(paragraph["bbox"][0], bbox[0]),
                min(paragraph["bbox"][1], bbox[1]),
                max(paragraph["bbox"][2], bbox[2]),
                max(paragraph["bbox"][3], bbox[3]),
            ]

            if line_num not in paragraph["lines"]:
                paragraph["lines"][line_num] = {"words": [], "bbox": bbox}

            line = paragraph["lines"][line_num]
            line["bbox"] = [
                min(line["bbox"][0], bbox[0]),
                min(line["bbox"][1], bbox[1]),
                max(line["bbox"][2], bbox[2]),
                max(line["bbox"][3], bbox[3]),
            ]

            if level == 5:
                if not text or confidence < self.min_confidence:
                    continue
                line["words"].append(
                    {
                        "text": text,
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                )

        structured_blocks = []
        for block_num in sorted(blocks.keys()):
            block = blocks[block_num]
            structured_paragraphs = []
            for par_num in sorted(block["paragraphs"].keys()):
                paragraph = block["paragraphs"][par_num]
                structured_lines = []
                for line_num in sorted(paragraph["lines"].keys()):
                    line = paragraph["lines"][line_num]
                    if line["words"]:
                        structured_lines.append({"words": line["words"], "bbox": line["bbox"]})
                if structured_lines:
                    structured_paragraphs.append(
                        {"lines": structured_lines, "bbox": paragraph["bbox"]}
                    )
            if structured_paragraphs:
                structured_blocks.append(
                    {"paragraphs": structured_paragraphs, "bbox": block["bbox"]}
                )

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
            return [self._format_output(self._image_to_data(single_img), include_recognition=True) for single_img in imgs]

        if det and not rec:
            return [self._format_output(self._image_to_data(single_img), include_recognition=False) for single_img in imgs]

        if not det and rec:
            return [[self._recognize_crop(single_img) for single_img in imgs]]

        raise ValueError("At least one of `det` or `rec` must be enabled.")

    def __call__(self, img, mfd_res=None):
        del mfd_res
        words = list(self._iter_segments(self._image_to_data(img)))
        if not words:
            return None, None
        line_results = self._merge_words_to_lines(words, include_recognition=True)
        boxes = [item[0] for item in line_results]
        rec_res = [item[1] for item in line_results]
        return boxes, rec_res

    def _image_to_data(self, img):
        if isinstance(img, np.ndarray):
            pil_img = Image.fromarray(img)
        elif isinstance(img, Image.Image):
            pil_img = img
        else:
            raise TypeError(f"Unsupported image type: {type(img)!r}")

        config_parts = [f"--oem {self.oem}", f"--psm {self.psm}"]
        if self.tessdata_dir:
            config_parts.append(f'--tessdata-dir "{self.tessdata_dir}"')
        if self.extra_config:
            config_parts.append(self.extra_config)

        return self.tesseract.image_to_data(
            pil_img,
            lang=self.lang,
            config=" ".join(config_parts),
            output_type=self.Output.DICT,
        )

    def _format_output(self, data, include_recognition: bool):
        words = list(self._iter_segments(data))
        return self._merge_words_to_lines(words, include_recognition=include_recognition)

    def _iter_segments(self, data):
        total = len(data.get("text", []))
        for idx in range(total):
            text = (data["text"][idx] or "").strip()
            confidence = self._normalize_confidence(data["conf"][idx])
            width = int(data["width"][idx])
            height = int(data["height"][idx])
            if not text or width <= 0 or height <= 0 or confidence < self.min_confidence:
                continue

            left = int(data["left"][idx])
            top = int(data["top"][idx])
            yield {
                "bbox": [left, top, left + width, top + height],
                "text": text,
                "score": confidence,
                "block_num": data["block_num"][idx],
                "par_num": data["par_num"][idx],
                "line_num": data["line_num"][idx],
            }

    def _merge_words_to_lines(self, words: list[dict], include_recognition: bool):
        grouped: dict[tuple[int, int, int], list[dict]] = {}
        for word in words:
            key = (word["block_num"], word["par_num"], word["line_num"])
            grouped.setdefault(key, []).append(word)

        merged = []
        for key in sorted(grouped.keys()):
            line_words = sorted(grouped[key], key=lambda item: (item["bbox"][1], item["bbox"][0]))
            bbox = [
                min(word["bbox"][0] for word in line_words),
                min(word["bbox"][1] for word in line_words),
                max(word["bbox"][2] for word in line_words),
                max(word["bbox"][3] for word in line_words),
            ]
            if include_recognition:
                text = " ".join(word["text"] for word in line_words).strip()
                score = (
                    sum(word["score"] for word in line_words) / len(line_words)
                    if line_words
                    else 0.0
                )
                merged.append([bbox, (text, score)])
            else:
                merged.append(bbox)
        return merged

    def _recognize_crop(self, img):
        data = self._image_to_data(img)
        words = list(self._iter_segments(data))
        if not words:
            return "", 0.0
        text = " ".join(word["text"] for word in words).strip()
        score = sum(word["score"] for word in words) / len(words)
        return text, score

    @staticmethod
    def _normalize_confidence(value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return confidence / 100 if confidence > 1 else confidence
