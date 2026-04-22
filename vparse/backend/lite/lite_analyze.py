# Copyright (c) Opendatalab. All rights reserved.
import time

import numpy as np
from loguru import logger

from vparse.model.ocr.tesseract import TesseractOCRModel
from vparse.utils.pdf_image_tools import load_images_from_pdf
from vparse.utils.enum_class import BlockType, ContentType, ImageType
from vparse.version import __version__


def doc_analyze(
    pdf_bytes,
    image_writer=None,
    lang="eng",
    **kwargs,
):
    del image_writer

    load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    load_images_time = round(time.time() - load_images_start, 2)
    logger.debug(
        f"load images cost: {load_images_time}, speed: {round(len(images_list) / load_images_time, 3)} images/s"
    )

    ocr_model = TesseractOCRModel(lang=lang, **kwargs)

    middle_json = {
        "pdf_info": [],
        "_backend": "lite",
        "_version_name": __version__,
    }

    infer_start = time.time()
    for idx, image_dict in enumerate(images_list):
        page = pdf_doc[idx]
        width, height = map(int, page.get_size())
        pil_img = image_dict["img_pil"]

        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        structured_data = ocr_model.get_structured_data(np.asarray(pil_img))

        para_blocks = []
        block_idx = 0
        for block in structured_data:
            for para in block["paragraphs"]:
                lines = []
                for line in para["lines"]:
                    spans = []
                    for word in line["words"]:
                        spans.append(
                            {
                                "type": ContentType.TEXT,
                                "content": word["text"],
                                "score": word["confidence"],
                                "bbox": word["bbox"],
                            }
                        )
                    if spans:
                        lines.append({"bbox": line["bbox"], "spans": spans})

                if lines:
                    para_blocks.append(
                        {
                            "index": block_idx,
                            "type": BlockType.TEXT,
                            "bbox": para["bbox"],
                            "lines": lines,
                        }
                    )
                    block_idx += 1

        middle_json["pdf_info"].append(
            {
                "preproc_blocks": para_blocks,
                "para_blocks": para_blocks,
                "discarded_blocks": [],
                "page_size": [width, height],
                "page_idx": idx,
            }
        )

    infer_time = round(time.time() - infer_start, 2)
    logger.debug(
        f"lite infer finished, cost: {infer_time}, speed: {round(len(images_list) / infer_time, 3)} page/s"
    )

    from vparse.utils.engine.processor import refine_middle_json
    middle_json = refine_middle_json(middle_json, pdf_doc=pdf_doc, lang=lang)
    return middle_json, None

import sys
_module = sys.modules[__name__]
sys.modules.setdefault("vparse.backend.lite.lite_analyze", _module)
sys.modules.setdefault("mineru.backend.lite.lite_analyze", _module)
