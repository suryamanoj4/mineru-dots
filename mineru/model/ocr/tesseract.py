# Copyright (c) Opendatalab. All rights reserved.
from __future__ import annotations

import shutil
from typing import Iterable

import numpy as np
from PIL import Image


class TesseractOCRModel:
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
        self.lang = lang
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
                formatted = self._format_output(data, include_recognition=False)
                results.append([item["box"] for item in formatted])
            return results

        if not det and rec:
            rec_results = []
            for single_img in imgs:
                rec_results.append(self._recognize_crop(single_img))
            return [rec_results]

        raise ValueError("At least one of `det` or `rec` must be enabled.")

    def __call__(self, img, mfd_res=None):
        del mfd_res
        data = self._image_to_data(img)
        segments = list(self._iter_segments(data))
        if not segments:
            return None, None
        dt_boxes = [item["box"] for item in segments]
        rec_res = [(item["text"], item["confidence"]) for item in segments]
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
    ) -> list[dict]:
        formatted = []
        for segment in self._iter_segments(data):
            entry = {"box": segment["box"]}
            if include_recognition:
                entry["rec"] = (segment["text"], segment["confidence"])
            formatted.append(entry)

        if include_recognition:
            return [[item["box"], item["rec"]] for item in formatted]
        return formatted

    def _iter_segments(self, data: dict) -> Iterable[dict]:
        total = len(data.get("text", []))
        for idx in range(total):
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
            }

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
