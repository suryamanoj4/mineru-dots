import os
import time

import cv2
import numpy as np
from loguru import logger

from vparse.backend.utils import cross_page_table_merge
from vparse.backend.vlm.vlm_magic_model import MagicModel
from vparse.utils.config_reader import get_table_enable, get_llm_aided_config
from vparse.utils.cut_image import cut_image_and_table
from vparse.utils.enum_class import ContentType
from vparse.utils.hash_utils import bytes_md5
from vparse.utils.pdf_image_tools import get_crop_img
from vparse.version import __version__


heading_level_import_success = False
llm_aided_config = get_llm_aided_config()
if llm_aided_config:
    title_aided_config = llm_aided_config.get('title_aided', {})
    if title_aided_config.get('enable', False):
        try:
            from vparse.utils.llm_aided import llm_aided_title
            from vparse.backend.pipeline.model_init import AtomModelSingleton
            heading_level_import_success = True
        except Exception as e:
            logger.warning("The heading level feature cannot be used. If you need to use the heading level feature, "
                            "please execute `pip install vparse[core]` to install the required packages.")


def blocks_to_page_info(page_blocks, image_dict, page, image_writer, page_index) -> dict:
    """Convert blocks to page information."""

    scale = image_dict["scale"]
    # page_pil_img = image_dict["img_pil"]
    page_pil_img = image_dict["img_pil"]
    page_img_md5 = bytes_md5(page_pil_img.tobytes())
    width, height = map(int, page.get_size())

    magic_model = MagicModel(page_blocks, width, height)
    image_blocks = magic_model.get_image_blocks()
    table_blocks = magic_model.get_table_blocks()
    title_blocks = magic_model.get_title_blocks()
    discarded_blocks = magic_model.get_discarded_blocks()
    code_blocks = magic_model.get_code_blocks()
    ref_text_blocks = magic_model.get_ref_text_blocks()
    phonetic_blocks = magic_model.get_phonetic_blocks()
    list_blocks = magic_model.get_list_blocks()

    # If title optimization is required, perform OCR detection on title_block crops.
    if heading_level_import_success:
        atom_model_manager = AtomModelSingleton()
        ocr_model = atom_model_manager.get_atom_model(
            atom_model_name='ocr',
            ocr_show_log=False,
            det_db_box_thresh=0.3,
            lang='ch_lite'
        )
        for title_block in title_blocks:
            title_pil_img = get_crop_img(title_block['bbox'], page_pil_img, scale)
            title_np_img = np.array(title_pil_img)
            # Add 50px white padding to title_np_img (top, bottom, left, right).
            title_np_img = cv2.copyMakeBorder(
                title_np_img, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )
            title_img = cv2.cvtColor(title_np_img, cv2.COLOR_RGB2BGR)
            ocr_det_res = ocr_model.ocr(title_img, rec=False)[0]
            if len(ocr_det_res) > 0:
                # Calculate the average height of all detection results.
                avg_height = np.mean([box[2][1] - box[0][1] for box in ocr_det_res])
                title_block['line_avg_height'] = round(avg_height/scale)

    text_blocks = magic_model.get_text_blocks()
    interline_equation_blocks = magic_model.get_interline_equation_blocks()

    all_spans = magic_model.get_all_spans()
    # Crop screenshots for image, table, and interline_equation spans.
    for span in all_spans:
        if span["type"] in [ContentType.IMAGE, ContentType.TABLE, ContentType.INTERLINE_EQUATION]:
            span = cut_image_and_table(span, page_pil_img, page_img_md5, page_index, image_writer, scale=scale)

    page_blocks = []
    page_blocks.extend([
        *image_blocks,
        *table_blocks,
        *code_blocks,
        *ref_text_blocks,
        *phonetic_blocks,
        *title_blocks,
        *text_blocks,
        *interline_equation_blocks,
        *list_blocks,
    ])
    # Sort page_blocks based on their index.
    page_blocks.sort(key=lambda x: x["index"])

    page_info = {"para_blocks": page_blocks, "discarded_blocks": discarded_blocks, "page_size": [width, height], "page_idx": page_index}
    return page_info


def result_to_middle_json(model_output_blocks_list, images_list, pdf_doc, image_writer):
    middle_json = {"pdf_info": [], "_backend":"vlm", "_version_name": __version__}
    for index, page_blocks in enumerate(model_output_blocks_list):
        page = pdf_doc[index]
        image_dict = images_list[index]
        page_info = blocks_to_page_info(page_blocks, image_dict, page, image_writer, index)
        middle_json["pdf_info"].append(page_info)

    """Table cross-page merge"""
    table_enable = get_table_enable(os.getenv('VPARSE_VLM_TABLE_ENABLE', 'True').lower() == 'true')
    if table_enable:
        cross_page_table_merge(middle_json["pdf_info"])

    """Optimize heading hierarchy using LLM."""
    if heading_level_import_success:
        llm_aided_title_start_time = time.time()
        llm_aided_title(middle_json["pdf_info"], title_aided_config)
        logger.info(f'llm aided title time: {round(time.time() - llm_aided_title_start_time, 2)}')

    # Close PDF document.
    pdf_doc.close()
    return middle_json