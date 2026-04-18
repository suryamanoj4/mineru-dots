#  Copyright (c) Opendatalab. All rights reserved.
import os
import time
from collections import defaultdict

import cv2
import numpy as np
from loguru import logger
from mineru_vl_utils import VParseClient
from mineru_vl_utils.structs import BlockType
from tqdm import tqdm

from vparse.backend.hybrid.hybrid_model_output_to_middle_json import (
    result_to_middle_json,
)
from vparse.backend.pipeline.model_init import HybridModelSingleton
from vparse.backend.vlm.vlm_analyze import ModelSingleton
from vparse.backend.vlm.dots_ocr_client import DotsOCRClient
from vparse.data.data_reader_writer import DataWriter
from vparse.utils.compat import get_env_with_legacy
from vparse.utils.config_reader import get_device
from vparse.utils.enum_class import ImageType, NotExtractType
from vparse.utils.model_utils import crop_img, get_vram, clean_memory
from vparse.utils.ocr_utils import (
    get_adjusted_mfdetrec_res,
    get_ocr_result_list,
    sorted_boxes,
    merge_det_boxes,
    update_det_boxes,
    OcrConfidence,
)
from vparse.utils.pdf_classify import classify
from vparse.utils.pdf_image_tools import load_images_from_pdf

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Allow MPS fallback
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"  # Disable albumentations update check

MFR_BASE_BATCH_SIZE = 16
OCR_DET_BASE_BATCH_SIZE = 16

not_extract_list = [item.value for item in NotExtractType]


def ocr_classify(
    pdf_bytes,
    parse_method: str = "auto",
) -> bool:
    # Determine OCR settings
    _ocr_enable = False
    if parse_method == "auto":
        if classify(pdf_bytes) == "ocr":
            _ocr_enable = True
    elif parse_method == "ocr":
        _ocr_enable = True
    return _ocr_enable


def ocr_det(
    hybrid_pipeline_model,
    np_images,
    results,
    mfd_res,
    _ocr_enable,
    batch_radio: int = 1,
):
    ocr_res_list = []
    if not hybrid_pipeline_model.enable_ocr_det_batch:
        # Non-batch mode - process page by page
        for np_image, page_mfd_res, page_results in tqdm(
            zip(np_images, mfd_res, results), total=len(np_images), desc="OCR-det"
        ):
            ocr_res_list.append([])
            img_height, img_width = np_image.shape[:2]
            for res in page_results:
                if res["type"] not in not_extract_list:
                    continue
                x0 = max(0, int(res["bbox"][0] * img_width))
                y0 = max(0, int(res["bbox"][1] * img_height))
                x1 = min(img_width, int(res["bbox"][2] * img_width))
                y1 = min(img_height, int(res["bbox"][3] * img_height))
                if x1 <= x0 or y1 <= y0:
                    continue
                res["poly"] = [x0, y0, x1, y0, x1, y1, x0, y1]
                new_image, useful_list = crop_img(
                    res, np_image, crop_paste_x=50, crop_paste_y=50
                )
                adjusted_mfdetrec_res = get_adjusted_mfdetrec_res(
                    page_mfd_res, useful_list
                )
                bgr_image = cv2.cvtColor(new_image, cv2.COLOR_RGB2BGR)
                ocr_res = hybrid_pipeline_model.ocr_model.ocr(
                    bgr_image, mfd_res=adjusted_mfdetrec_res, rec=False
                )[0]
                if ocr_res:
                    ocr_result_list = get_ocr_result_list(
                        ocr_res,
                        useful_list,
                        _ocr_enable,
                        bgr_image,
                        hybrid_pipeline_model.lang,
                    )

                    ocr_res_list[-1].extend(ocr_result_list)
    else:
        # Batch mode - group by language and resolution
        # Collect all cropped images that need OCR detection
        all_cropped_images_info = []

        for np_image, page_mfd_res, page_results in zip(np_images, mfd_res, results):
            ocr_res_list.append([])
            img_height, img_width = np_image.shape[:2]
            for res in page_results:
                if res["type"] not in not_extract_list:
                    continue
                x0 = max(0, int(res["bbox"][0] * img_width))
                y0 = max(0, int(res["bbox"][1] * img_height))
                x1 = min(img_width, int(res["bbox"][2] * img_width))
                y1 = min(img_height, int(res["bbox"][3] * img_height))
                if x1 <= x0 or y1 <= y0:
                    continue
                res["poly"] = [x0, y0, x1, y0, x1, y1, x0, y1]
                new_image, useful_list = crop_img(
                    res, np_image, crop_paste_x=50, crop_paste_y=50
                )
                adjusted_mfdetrec_res = get_adjusted_mfdetrec_res(
                    page_mfd_res, useful_list
                )
                bgr_image = cv2.cvtColor(new_image, cv2.COLOR_RGB2BGR)
                all_cropped_images_info.append(
                    (bgr_image, useful_list, adjusted_mfdetrec_res, ocr_res_list[-1])
                )

        # Group by resolution and perform padding simultaneously
        RESOLUTION_GROUP_STRIDE = 64  # 32

        resolution_groups = defaultdict(list)
        for crop_info in all_cropped_images_info:
            cropped_img = crop_info[0]
            h, w = cropped_img.shape[:2]
            # Directly calculate target dimensions and use as group key
            target_h = (
                (h + RESOLUTION_GROUP_STRIDE - 1) // RESOLUTION_GROUP_STRIDE
            ) * RESOLUTION_GROUP_STRIDE
            target_w = (
                (w + RESOLUTION_GROUP_STRIDE - 1) // RESOLUTION_GROUP_STRIDE
            ) * RESOLUTION_GROUP_STRIDE
            group_key = (target_h, target_w)
            resolution_groups[group_key].append(crop_info)

        # Batch process each resolution group
        for (target_h, target_w), group_crops in tqdm(
            resolution_groups.items(), desc=f"OCR-det"
        ):
            # Pad all images to a uniform size
            batch_images = []
            for crop_info in group_crops:
                img = crop_info[0]
                h, w = img.shape[:2]
                # Create a white background of target dimensions
                padded_img = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255
                padded_img[:h, :w] = img
                batch_images.append(padded_img)

            # Batch detection
            det_batch_size = min(
                len(batch_images), batch_radio * OCR_DET_BASE_BATCH_SIZE
            )
            batch_results = hybrid_pipeline_model.ocr_model.text_detector.batch_predict(
                batch_images, det_batch_size
            )

            # Process batch results
            for crop_info, (dt_boxes, _) in zip(group_crops, batch_results):
                bgr_image, useful_list, adjusted_mfdetrec_res, ocr_page_res_list = (
                    crop_info
                )

                if dt_boxes is not None and len(dt_boxes) > 0:
                    # Process detection boxes
                    dt_boxes_sorted = sorted_boxes(dt_boxes)
                    dt_boxes_merged = (
                        merge_det_boxes(dt_boxes_sorted) if dt_boxes_sorted else []
                    )

                    # Update detection boxes based on formula positions
                    dt_boxes_final = (
                        update_det_boxes(dt_boxes_merged, adjusted_mfdetrec_res)
                        if dt_boxes_merged and adjusted_mfdetrec_res
                        else dt_boxes_merged
                    )

                    if dt_boxes_final:
                        ocr_res = [
                            box.tolist() if hasattr(box, "tolist") else box
                            for box in dt_boxes_final
                        ]
                        ocr_result_list = get_ocr_result_list(
                            ocr_res,
                            useful_list,
                            _ocr_enable,
                            bgr_image,
                            hybrid_pipeline_model.lang,
                        )
                        ocr_page_res_list.extend(ocr_result_list)
    return ocr_res_list


def mask_image_regions(np_images, results):
    # Based on the VLM results, mask image, table, and equation blocks into white background images in each page
    for np_image, vlm_page_results in zip(np_images, results):
        img_height, img_width = np_image.shape[:2]
        # Collect regions that need masking
        mask_regions = []
        for block in vlm_page_results:
            if block["type"] in [BlockType.IMAGE, BlockType.TABLE, BlockType.EQUATION]:
                bbox = block["bbox"]
                # Batch convert normalized coordinates to pixel coordinates and perform boundary checks
                x0 = max(0, int(bbox[0] * img_width))
                y0 = max(0, int(bbox[1] * img_height))
                x1 = min(img_width, int(bbox[2] * img_width))
                y1 = min(img_height, int(bbox[3] * img_height))
                # Add only valid regions
                if x1 > x0 and y1 > y0:
                    mask_regions.append((y0, y1, x0, x1))
        # Apply masks in batch
        for y0, y1, x0, x1 in mask_regions:
            np_image[y0:y1, x0:x1, :] = 255
    return np_images


def normalize_poly_to_bbox(item, page_width, page_height):
    """Normalize poly coordinates to bbox"""
    poly = item["poly"]
    x0 = min(max(poly[0] / page_width, 0), 1)
    y0 = min(max(poly[1] / page_height, 0), 1)
    x1 = min(max(poly[4] / page_width, 0), 1)
    y1 = min(max(poly[5] / page_height, 0), 1)
    item["bbox"] = [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]
    item.pop("poly", None)


def _process_ocr_and_formulas(
    images_pil_list,
    results,
    language,
    inline_formula_enable,
    _ocr_enable,
    batch_radio: int = 1,
):
    """Process OCR and formula recognition"""

    # Traverse results, take screenshots of text blocks and hand over to OCR for recognition
    # Decide whether to enable det only or det+rec based on _ocr_enable
    # Decide whether to use a combination of MFD and OCR or pure OCR based on inline_formula_enable

    # Convert PIL images to numpy arrays
    np_images = [np.asarray(pil_image).copy() for pil_image in images_pil_list]

    # Get hybrid model instance
    hybrid_model_singleton = HybridModelSingleton()
    hybrid_pipeline_model = hybrid_model_singleton.get_model(
        lang=language,
        formula_enable=inline_formula_enable,
    )

    if inline_formula_enable:
        # Before performing inline formula detection and recognition, mask the images, tables, and interline formula regions in the image.
        np_images = mask_image_regions(np_images, results)
        # Formula detection
        images_mfd_res = hybrid_pipeline_model.mfd_model.batch_predict(
            np_images, batch_size=1, conf=0.5
        )
        # Formula recognition
        inline_formula_list = hybrid_pipeline_model.mfr_model.batch_predict(

            images_mfd_res,
            np_images,
            batch_size=batch_radio * MFR_BASE_BATCH_SIZE,
            interline_enable=True,
        )
    else:
        inline_formula_list = [[] for _ in range(len(images_pil_list))]

    mfd_res = []
    for page_inline_formula_list in inline_formula_list:
        page_mfd_res = []
        for formula in page_inline_formula_list:
            formula["category_id"] = 13
            page_mfd_res.append(
                {
                    "bbox": [
                        int(formula["poly"][0]),
                        int(formula["poly"][1]),
                        int(formula["poly"][4]),
                        int(formula["poly"][5]),
                    ],
                }
            )
        mfd_res.append(page_mfd_res)

    # VLM did not perform OCR, ocr_det is needed
    ocr_res_list = ocr_det(
        hybrid_pipeline_model,
        np_images,
        results,
        mfd_res,
        _ocr_enable,
        batch_radio=batch_radio,
    )

    # If OCR is needed, perform ocr_rec
    if _ocr_enable:
        need_ocr_list = []
        img_crop_list = []
        for page_ocr_res_list in ocr_res_list:
            for ocr_res in page_ocr_res_list:
                if "np_img" in ocr_res:
                    need_ocr_list.append(ocr_res)
                    img_crop_list.append(ocr_res.pop("np_img"))
        if len(img_crop_list) > 0:
            # Process OCR
            ocr_result_list = hybrid_pipeline_model.ocr_model.ocr(
                img_crop_list, det=False, tqdm_enable=True
            )[0]

            # Verify we have matching counts
            assert len(ocr_result_list) == len(need_ocr_list), (
                f"ocr_result_list: {len(ocr_result_list)}, need_ocr_list: {len(need_ocr_list)}"
            )

            # Process OCR results for this language
            for index, need_ocr_res in enumerate(need_ocr_list):
                ocr_text, ocr_score = ocr_result_list[index]
                need_ocr_res["text"] = ocr_text
                need_ocr_res["score"] = float(f"{ocr_score:.3f}")
                if ocr_score < OcrConfidence.min_confidence:
                    need_ocr_res["category_id"] = 16
                else:
                    layout_res_bbox = [
                        need_ocr_res["poly"][0],
                        need_ocr_res["poly"][1],
                        need_ocr_res["poly"][4],
                        need_ocr_res["poly"][5],
                    ]
                    layout_res_width = layout_res_bbox[2] - layout_res_bbox[0]
                    layout_res_height = layout_res_bbox[3] - layout_res_bbox[1]
                    if (
                        ocr_text
                        in [
                            "（204号",
                            "（20",
                            "（2",
                            "（2号",
                            "（20号",
                            "号",
                            "（204",
                            "(cid:)",
                            "(ci:)",
                            "(cd:1)",
                            "cd:)",
                            "c)",
                            "(cd:)",
                            "c",
                            "id:)",
                            ":)",
                            "√:)",
                            "√i:)",
                            "−i:)",
                            "−:",
                            "i:)",
                        ]
                        and ocr_score < 0.8
                        and layout_res_width < layout_res_height
                    ):
                        need_ocr_res["category_id"] = 16

    return inline_formula_list, ocr_res_list, hybrid_pipeline_model


def _normalize_bbox(
    inline_formula_list,
    ocr_res_list,
    images_pil_list,
):
    """Normalize coordinates and generate final results"""
    for page_inline_formula_list, page_ocr_res_list, page_pil_image in zip(
        inline_formula_list, ocr_res_list, images_pil_list
    ):
        if page_inline_formula_list or page_ocr_res_list:
            page_width, page_height = page_pil_image.size
            # Process formula list
            for formula in page_inline_formula_list:
                normalize_poly_to_bbox(formula, page_width, page_height)
            # Process OCR results list
            for ocr_res in page_ocr_res_list:
                normalize_poly_to_bbox(ocr_res, page_width, page_height)


def get_batch_ratio(device):
    """
    Get batch ratio based on VRAM size or environment variables
    """
    # 1. Try to get from environment variables first
    """
    c/s架构分离部署时，建议通过设置环境变量 VPARSE_HYBRID_BATCH_RATIO 来指定 batch ratio
    建议的设置值如如下，以下配置值已考虑一定的冗余，单卡多终端部署时为了保证稳定性，可以额外保留一个client端的显存作为整体冗余
    单个client端显存大小 | VPARSE_HYBRID_BATCH_RATIO
    ------------------|------------------------
    <= 6   GB         | 8
    <= 4.5 GB         | 4
    <= 3   GB         | 2
    <= 2.5 GB         | 1
    例如：
    export VPARSE_HYBRID_BATCH_RATIO=4
    """
    env_val = get_env_with_legacy("VPARSE_HYBRID_BATCH_RATIO", "MINERU_HYBRID_BATCH_RATIO")
    if env_val:
        try:
            batch_ratio = int(env_val)
            logger.info(f"hybrid batch ratio (from env): {batch_ratio}")
            return batch_ratio
        except ValueError as e:
            logger.warning(
                f"Invalid VPARSE_HYBRID_BATCH_RATIO value: {env_val}, switching to auto mode. Error: {e}"
            )

    # 2. Infer automatically based on VRAM
    """
    Roughly estimate batch ratio based on total VRAM, excluding memory occupied by inference frameworks like vLLM.
    """
    gpu_memory = get_vram(device)
    if gpu_memory >= 32:
        batch_ratio = 16
    elif gpu_memory >= 16:
        batch_ratio = 8
    elif gpu_memory >= 12:
        batch_ratio = 4
    elif gpu_memory >= 8:
        batch_ratio = 2
    else:
        batch_ratio = 1

    logger.info(f"hybrid batch ratio (auto, vram={gpu_memory}GB): {batch_ratio}")
    return batch_ratio


def _should_enable_vlm_ocr(
    ocr_enable: bool, language: str, inline_formula_enable: bool
) -> bool:
    """判断是否启用VLM OCR"""
    force_enable = get_env_with_legacy("VPARSE_FORCE_VLM_OCR_ENABLE", "MINERU_FORCE_VLM_OCR_ENABLE", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    if force_enable:
        return True

    force_pipeline = get_env_with_legacy("VPARSE_HYBRID_FORCE_PIPELINE_ENABLE", "MINERU_HYBRID_FORCE_PIPELINE_ENABLE", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    return (
        ocr_enable
        and language in ["ch", "en"]
        and inline_formula_enable
        and not force_pipeline
    )


def doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="transformers",
    parse_method: str = "auto",
    language: str = "ch",
    inline_formula_enable: bool = True,
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    # Initialize predictor
    if predictor is None:
        predictor = ModelSingleton().get_model(
            backend, model_path, server_url, **kwargs
        )

    # Load images
    load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
    load_images_time = round(time.time() - load_images_start, 2)
    logger.debug(
        f"load images cost: {load_images_time}, speed: {round(len(images_pil_list) / load_images_time, 3)} images/s"
    )

    # Get device information
    device = get_device()

    # Determine OCR configuration
    _ocr_enable = ocr_classify(pdf_bytes, parse_method=parse_method)
    _vlm_ocr_enable = _should_enable_vlm_ocr(
        _ocr_enable, language, inline_formula_enable
    )

    # For dots.ocr: use prompt_layout_only_en when _vlm_ocr_enable is False (hybrid mode with pipeline OCR)
    if (
        hasattr(predictor, "__class__")
        and predictor.__class__.__name__ == "DotsOCRClient"
    ):
        prompt_mode = (
            "prompt_layout_only_en" if not _vlm_ocr_enable else "prompt_layout_all_en"
        )

    infer_start = time.time()
    # VLM extraction
    if _vlm_ocr_enable:
        results = predictor.batch_two_step_extract(
            images=images_pil_list, prompt_mode=prompt_mode
        )
        hybrid_pipeline_model = None
        inline_formula_list = [[] for _ in images_pil_list]
        ocr_res_list = [[] for _ in images_pil_list]
    else:
        batch_ratio = get_batch_ratio(device)
        results = predictor.batch_two_step_extract(
            images=images_pil_list,
            prompt_mode=prompt_mode,
            not_extract_list=not_extract_list,
        )
        inline_formula_list, ocr_res_list, hybrid_pipeline_model = (
            _process_ocr_and_formulas(
                images_pil_list,
                results,
                language,
                inline_formula_enable,
                _ocr_enable,
                batch_radio=batch_ratio,
            )
        )
        _normalize_bbox(inline_formula_list, ocr_res_list, images_pil_list)
    infer_time = round(time.time() - infer_start, 2)
    logger.debug(
        f"infer finished, cost: {infer_time}, speed: {round(len(results) / infer_time, 3)} page/s"
    )

    # Generate middle JSON
    middle_json = result_to_middle_json(
        results,
        inline_formula_list,
        ocr_res_list,
        images_list,
        pdf_doc,
        image_writer,
        _ocr_enable,
        _vlm_ocr_enable,
        hybrid_pipeline_model,
    )

    clean_memory(device)
    return middle_json, results, _vlm_ocr_enable


async def aio_doc_analyze(
    pdf_bytes,
    image_writer: DataWriter | None,
    predictor=None,
    backend="transformers",
    parse_method: str = "auto",
    language: str = "ch",
    inline_formula_enable: bool = True,
    model_path: str | None = None,
    server_url: str | None = None,
    prompt_mode: str = "prompt_layout_all_en",
    **kwargs,
):
    # Initialize predictor
    if predictor is None:
        predictor = ModelSingleton().get_model(
            backend, model_path, server_url, **kwargs
        )

    # Load images
    load_images_start = time.time()
    images_list, pdf_doc = load_images_from_pdf(pdf_bytes, image_type=ImageType.PIL)
    images_pil_list = [image_dict["img_pil"] for image_dict in images_list]
    load_images_time = round(time.time() - load_images_start, 2)
    logger.debug(
        f"load images cost: {load_images_time}, speed: {round(len(images_pil_list) / load_images_time, 3)} images/s"
    )

    # Get device information
    device = get_device()

    # Determine OCR configuration
    _ocr_enable = ocr_classify(pdf_bytes, parse_method=parse_method)
    _vlm_ocr_enable = _should_enable_vlm_ocr(
        _ocr_enable, language, inline_formula_enable
    )

    # For dots.ocr: use prompt_layout_only_en when _vlm_ocr_enable is False (hybrid mode with pipeline OCR)
    if isinstance(predictor, DotsOCRClient):
        prompt_mode = (
            "prompt_layout_only_en" if not _vlm_ocr_enable else "prompt_layout_all_en"
        )

    infer_start = time.time()
    # VLM extraction
    if _vlm_ocr_enable:
        results = await predictor.aio_batch_two_step_extract(
            images=images_pil_list, prompt_mode=prompt_mode
        )
        hybrid_pipeline_model = None
        inline_formula_list = [[] for _ in images_pil_list]
        ocr_res_list = [[] for _ in images_pil_list]
    else:
        batch_ratio = get_batch_ratio(device)
        results = await predictor.aio_batch_two_step_extract(
            images=images_pil_list,
            prompt_mode=prompt_mode,
            not_extract_list=not_extract_list,
        )
        inline_formula_list, ocr_res_list, hybrid_pipeline_model = (
            _process_ocr_and_formulas(
                images_pil_list,
                results,
                language,
                inline_formula_enable,
                _ocr_enable,
                batch_radio=batch_ratio,
            )
        )
        _normalize_bbox(inline_formula_list, ocr_res_list, images_pil_list)
    infer_time = round(time.time() - infer_start, 2)
    logger.debug(
        f"infer finished, cost: {infer_time}, speed: {round(len(results) / infer_time, 3)} page/s"
    )

    # Generate middle JSON
    middle_json = result_to_middle_json(
        results,
        inline_formula_list,
        ocr_res_list,
        images_list,
        pdf_doc,
        image_writer,
        _ocr_enable,
        _vlm_ocr_enable,
        hybrid_pipeline_model,
    )

    clean_memory(device)
    return middle_json, results, _vlm_ocr_enable
