# Copyright (c) Opendatalab. All rights reserved.
import time
from loguru import logger
import numpy as np
from PIL import Image

from mineru.model.ocr.tesseract import TesseractOCRModel
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.utils.enum_class import ImageType, BlockType, ContentType
from mineru.version import __version__


def doc_analyze(
    pdf_bytes,
    image_writer=None,
    lang="eng",
    **kwargs,
):
    """Direct Tesseract-only backend analysis."""
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
        "_version_name": __version__
    }
    
    infer_start = time.time()
    for idx, image_dict in enumerate(images_list):
        page = pdf_doc[idx]
        width, height = map(int, page.get_size())
        pil_img = image_dict["img_pil"]
        
        # Tesseract works best with RGB
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        
        np_img = np.asarray(pil_img)
        structured_data = ocr_model.get_structured_data(np_img)
        
        para_blocks = []
        block_idx = 0
        for block in structured_data:
            for para in block["paragraphs"]:
                lines = []
                for line in para["lines"]:
                    spans = []
                    for word in line["words"]:
                        spans.append({
                            "type": ContentType.TEXT,
                            "content": word["text"],
                            "score": word["confidence"],
                            "bbox": word["bbox"]
                        })
                    if spans:
                        lines.append({
                            "bbox": line["bbox"],
                            "spans": spans
                        })
                
                if lines:
                    para_blocks.append({
                        "index": block_idx,
                        "type": BlockType.TEXT,
                        "bbox": para["bbox"],
                        "lines": lines
                    })
                    block_idx += 1
        
        page_info = {
            "preproc_blocks": para_blocks,
            "para_blocks": para_blocks,
            "discarded_blocks": [],
            "page_size": [width, height],
            "page_idx": idx
        }
        middle_json["pdf_info"].append(page_info)
        
    infer_time = round(time.time() - infer_start, 2)
    logger.debug(
        f"lite infer finished, cost: {infer_time}, speed: {round(len(images_list) / infer_time, 3)} page/s"
    )
    
    pdf_doc.close()
    return middle_json, None
