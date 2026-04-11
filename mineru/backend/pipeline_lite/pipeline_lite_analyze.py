# Copyright (c) Opendatalab. All rights reserved.
import os
from dataclasses import dataclass

from loguru import logger

from mineru.model.ocr import TesseractOCRModel
from mineru.utils.enum_class import BlockType, ContentType, ImageType
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.version import __version__


PIPELINE_TO_TESSERACT_LANG = {
    "ch": "chi_sim+eng",
    "ch_server": "chi_sim+eng",
    "ch_lite": "chi_sim+eng",
    "en": "eng",
    "korean": "kor+eng",
    "japan": "jpn+eng",
    "chinese_cht": "chi_tra+eng",
    "ta": "tam+eng",
    "te": "tel+eng",
    "ka": "kan+eng",
    "th": "tha+eng",
    "el": "ell+eng",
    "latin": "eng",
    "arabic": "ara+eng",
    "east_slavic": "rus+eng",
    "cyrillic": "rus+eng",
    "devanagari": "hin+eng",
}


@dataclass(frozen=True)
class TesseractConfig:
    lang: str
    oem: int
    psm: int
    config: str
    tesseract_cmd: str | None
    tessdata_dir: str | None
    min_confidence: float


def doc_analyze(
    pdf_bytes: bytes,
    language: str = "ch",
    parse_method: str = "auto",
    **kwargs,
):
    del parse_method

    config = _build_tesseract_config(language=language, **kwargs)
    logger.info(
        f"lite backend using direct Tesseract lang={config.lang} oem={config.oem} psm={config.psm}"
    )

    ocr_model = TesseractOCRModel(
        lang=config.lang,
        oem=config.oem,
        psm=config.psm,
        config=config.config,
        tesseract_cmd=config.tesseract_cmd,
        tessdata_dir=config.tessdata_dir,
        min_confidence=config.min_confidence,
    )

    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    try:
        page_outputs = []
        page_infos = []
        for page_index, image_dict in enumerate(images_list):
            page_output, page_info = _analyze_page(
                image_dict=image_dict,
                page=pdf_doc[page_index],
                page_index=page_index,
                ocr_model=ocr_model,
            )
            page_outputs.append(page_output)
            page_infos.append(page_info)

        middle_json = {
            "pdf_info": page_infos,
            "_backend": "lite",
            "_version_name": __version__,
            "_backend_config": _config_to_dict(config),
        }
        raw_output = {
            "_backend": "lite",
            "_ocr_engine": "tesseract",
            "_backend_config": _config_to_dict(config),
            "pages": page_outputs,
        }
        return middle_json, raw_output
    finally:
        pdf_doc.close()


def _analyze_page(image_dict, page, page_index: int, ocr_model: TesseractOCRModel):
    words = ocr_model.predict(image_dict["img_pil"])
    page_width, page_height = map(int, page.get_size())
    line_items = _group_words_into_lines(words)
    para_blocks = _group_lines_into_paragraphs(line_items, page_width)

    page_output = {
        "page_idx": page_index,
        "page_size": [page_width, page_height],
        "words": [
            {
                "text": word["text"],
                "confidence": word["confidence"],
                "bbox": _quad_to_bbox(word["box"]),
                "quad": word["box"],
                "block_num": word.get("block_num", 0),
                "par_num": word.get("par_num", 0),
                "line_num": word.get("line_num", 0),
                "word_num": word.get("word_num", 0),
            }
            for word in words
        ],
        "lines": [
            {
                "text": line["text"],
                "confidence": line["confidence"],
                "bbox": line["bbox"],
                "word_count": len(line["words"]),
            }
            for line in line_items
        ],
    }
    page_info = {
        "para_blocks": para_blocks,
        "discarded_blocks": [],
        "page_size": [page_width, page_height],
        "page_idx": page_index,
    }
    return page_output, page_info


def _group_words_into_lines(words: list[dict]) -> list[dict]:
    line_groups: dict[tuple[int, int, int], list[dict]] = {}
    fallback_index = 0
    for word in words:
        key = (
            int(word.get("block_num", 0) or 0),
            int(word.get("par_num", 0) or 0),
            int(word.get("line_num", 0) or 0),
        )
        if key == (0, 0, 0):
            key = (10**9, 10**9, fallback_index)
            fallback_index += 1
        line_groups.setdefault(key, []).append(word)

    lines = []
    for key, line_words in line_groups.items():
        sorted_words = sorted(
            line_words,
            key=lambda item: (_quad_to_bbox(item["box"])[0], _quad_to_bbox(item["box"])[1]),
        )
        text = " ".join(word["text"] for word in sorted_words).strip()
        if not text:
            continue
        lines.append(
            {
                "key": key,
                "bbox": _merge_bboxes([_quad_to_bbox(word["box"]) for word in sorted_words]),
                "text": text,
                "confidence": round(
                    sum(word["confidence"] for word in sorted_words) / len(sorted_words), 3
                ),
                "words": sorted_words,
            }
        )

    lines.sort(key=lambda item: (item["bbox"][1], item["bbox"][0], item["key"]))
    return lines


def _group_lines_into_paragraphs(lines: list[dict], page_width: int) -> list[dict]:
    if not lines:
        return []

    blocks = []
    current_lines = []
    prev_line = None

    for line in lines:
        start_new_block = False
        if prev_line is not None:
            prev_height = max(1, prev_line["bbox"][3] - prev_line["bbox"][1])
            curr_height = max(1, line["bbox"][3] - line["bbox"][1])
            gap = line["bbox"][1] - prev_line["bbox"][3]
            indent_delta = abs(line["bbox"][0] - prev_line["bbox"][0])
            if gap > max(prev_height, curr_height) * 0.9:
                start_new_block = True
            elif indent_delta > max(24, int(page_width * 0.04)) and gap > max(6, int(curr_height * 0.25)):
                start_new_block = True

        if start_new_block and current_lines:
            blocks.append(_make_para_block(current_lines))
            current_lines = []

        current_lines.append(line)
        prev_line = line

    if current_lines:
        blocks.append(_make_para_block(current_lines))

    return blocks


def _make_para_block(lines: list[dict]) -> dict:
    return {
        "type": BlockType.TEXT,
        "bbox": _merge_bboxes([line["bbox"] for line in lines]),
        "confidence": round(
            sum(line["confidence"] for line in lines) / len(lines), 3
        ),
        "lines": [
            {
                "bbox": line["bbox"],
                "spans": [
                    {
                        "type": ContentType.TEXT,
                        "content": word["text"],
                        "bbox": _quad_to_bbox(word["box"]),
                        "score": word["confidence"],
                    }
                    for word in line["words"]
                ],
            }
            for line in lines
        ],
    }


def _build_tesseract_config(language: str = "ch", **kwargs) -> TesseractConfig:
    lang = _first_non_empty(
        kwargs.get("tesseract_lang"),
        os.getenv("MINERU_TESSERACT_LANG"),
        _map_pipeline_lang(language),
    )
    oem = _parse_int(
        _first_non_empty(kwargs.get("tesseract_oem"), os.getenv("MINERU_TESSERACT_OEM"), 3),
        "tesseract_oem",
    )
    psm = _parse_int(
        _first_non_empty(kwargs.get("tesseract_psm"), os.getenv("MINERU_TESSERACT_PSM"), 3),
        "tesseract_psm",
    )
    config = str(
        _first_non_empty(kwargs.get("tesseract_config"), os.getenv("MINERU_TESSERACT_CONFIG"), "")
    ).strip()
    tesseract_cmd = _optional_str(
        _first_non_empty(kwargs.get("tesseract_cmd"), os.getenv("MINERU_TESSERACT_CMD"))
    )
    tessdata_dir = _optional_str(
        _first_non_empty(kwargs.get("tessdata_dir"), os.getenv("MINERU_TESSDATA_DIR"))
    )
    min_confidence = _parse_float(
        _first_non_empty(
            kwargs.get("tesseract_min_confidence"),
            os.getenv("MINERU_TESSERACT_MIN_CONFIDENCE"),
            0.0,
        ),
        "tesseract_min_confidence",
    )

    if not lang:
        raise ValueError("Invalid backend configuration: `tesseract_lang` must not be empty.")
    if oem < 0:
        raise ValueError("Invalid backend configuration: `tesseract_oem` must be >= 0.")
    if psm < 0:
        raise ValueError("Invalid backend configuration: `tesseract_psm` must be >= 0.")
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError(
            "Invalid backend configuration: `tesseract_min_confidence` must be between 0 and 1."
        )

    return TesseractConfig(
        lang=str(lang).strip(),
        oem=oem,
        psm=psm,
        config=config,
        tesseract_cmd=tesseract_cmd,
        tessdata_dir=tessdata_dir,
        min_confidence=min_confidence,
    )


def _map_pipeline_lang(language: str | None) -> str:
    if not language:
        return "eng"
    return PIPELINE_TO_TESSERACT_LANG.get(language, language)


def _config_to_dict(config: TesseractConfig) -> dict:
    return {
        "ocr_engine": "tesseract",
        "lang": config.lang,
        "oem": config.oem,
        "psm": config.psm,
        "extra_config": config.config,
        "tesseract_cmd": config.tesseract_cmd,
        "tessdata_dir": config.tessdata_dir,
        "min_confidence": config.min_confidence,
    }


def _first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def _optional_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_int(value, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid backend configuration: `{name}` must be an integer."
        ) from exc


def _parse_float(value, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid backend configuration: `{name}` must be a number."
        ) from exc


def _quad_to_bbox(box: list[list[int]]) -> list[int]:
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def _merge_bboxes(bboxes: list[list[int]]) -> list[int]:
    x0 = min(bbox[0] for bbox in bboxes)
    y0 = min(bbox[1] for bbox in bboxes)
    x1 = max(bbox[2] for bbox in bboxes)
    y1 = max(bbox[3] for bbox in bboxes)
    return [int(x0), int(y0), int(x1), int(y1)]
