# Copyright (c) Opendatalab. All rights reserved.
import os
import time

from loguru import logger
from tqdm import tqdm

from vparse.backend.utils import cross_page_table_merge
from vparse.utils.config_reader import get_device, get_llm_aided_config, get_formula_enable
from vparse.backend.pipeline.model_init import AtomModelSingleton
from vparse.backend.pipeline.para_split import para_split
from vparse.utils.block_pre_proc import prepare_block_bboxes, process_groups
from vparse.utils.block_sort import sort_blocks_by_bbox
from vparse.utils.boxbase import calculate_overlap_area_in_bbox1_area_ratio
from vparse.utils.cut_image import cut_image_and_table
from vparse.utils.enum_class import ContentType
from vparse.utils.llm_aided import llm_aided_title
from vparse.utils.model_utils import clean_memory
from vparse.backend.pipeline.pipeline_magic_model import MagicModel
from vparse.utils.ocr_utils import OcrConfidence
from vparse.utils.span_block_fix import fill_spans_in_blocks, fix_discarded_block, fix_block_spans
from vparse.utils.span_pre_proc import remove_outside_spans, remove_overlaps_low_confidence_spans, \
    remove_overlaps_min_spans, txt_spans_extract
from vparse.version import __version__
from vparse.utils.hash_utils import bytes_md5


def page_model_info_to_page_info(page_model_info, image_dict, page, image_writer, page_index, ocr_enable=False, formula_enabled=True):
    scale = image_dict["scale"]
    page_pil_img = image_dict["img_pil"]
    # page_img_md5 = str_md5(image_dict["img_base64"])
    page_img_md5 = bytes_md5(page_pil_img.tobytes())
    page_w, page_h = map(int, page.get_size())
    magic_model = MagicModel(page_model_info, scale)

    # Retrieve block information from the magic_model object for later use
    discarded_blocks = magic_model.get_discarded()
    text_blocks = magic_model.get_text_blocks()
    title_blocks = magic_model.get_title_blocks()
    inline_equations, interline_equations, interline_equation_blocks = magic_model.get_equations()

    img_groups = magic_model.get_imgs()
    table_groups = magic_model.get_tables()

    # Group image and table blocks
    img_body_blocks, img_caption_blocks, img_footnote_blocks, maybe_text_image_blocks = process_groups(
        img_groups, 'image_body', 'image_caption_list', 'image_footnote_list'
    )

    table_body_blocks, table_caption_blocks, table_footnote_blocks, _ = process_groups(
        table_groups, 'table_body', 'table_caption_list', 'table_footnote_list'
    )

    # Get information for all spans
    spans = magic_model.get_all_spans()

    # Some images may be text blocks; determine using simple rules
    if len(maybe_text_image_blocks) > 0:
        for block in maybe_text_image_blocks:
            should_add_to_text_blocks = False

            if ocr_enable:
                # Find text spans overlapping with the current block
                span_in_block_list = [
                    span for span in spans
                    if span['type'] == 'text' and
                       calculate_overlap_area_in_bbox1_area_ratio(span['bbox'], block['bbox']) > 0.7
                ]

                if len(span_in_block_list) > 0:
                    # Calculate total area of spans
                    spans_area = sum(
                        (span['bbox'][2] - span['bbox'][0]) * (span['bbox'][3] - span['bbox'][1])
                        for span in span_in_block_list
                    )

                    # Calculate block area
                    block_area = (block['bbox'][2] - block['bbox'][0]) * (block['bbox'][3] - block['bbox'][1])

                    # Determine if it meets text-image criteria
                    if block_area > 0 and spans_area / block_area > 0.25:
                        should_add_to_text_blocks = True

            # Add to appropriate list based on criteria
            if should_add_to_text_blocks:
                block.pop('group_id', None)  # Remove group_id
                text_blocks.append(block)
            else:
                img_body_blocks.append(block)


    # Consolidate bboxes for all blocks
    if formula_enabled:
        interline_equation_blocks = []

    if len(interline_equation_blocks) > 0:

        for block in interline_equation_blocks:
            spans.append({
                "type": ContentType.INTERLINE_EQUATION,
                'score': block['score'],
                "bbox": block['bbox'],
                "content": "",
            })

        all_bboxes, all_discarded_blocks, footnote_blocks = prepare_block_bboxes(
            img_body_blocks, img_caption_blocks, img_footnote_blocks,
            table_body_blocks, table_caption_blocks, table_footnote_blocks,
            discarded_blocks,
            text_blocks,
            title_blocks,
            interline_equation_blocks,
            page_w,
            page_h,
        )
    else:
        all_bboxes, all_discarded_blocks, footnote_blocks = prepare_block_bboxes(
            img_body_blocks, img_caption_blocks, img_footnote_blocks,
            table_body_blocks, table_caption_blocks, table_footnote_blocks,
            discarded_blocks,
            text_blocks,
            title_blocks,
            interline_equations,
            page_w,
            page_h,
        )

    # Filter image and table spans using image_body and table_body blocks before removing duplicates
    # Also remove large watermarks while preserving 'abandon' spans
    spans = remove_outside_spans(spans, all_bboxes, all_discarded_blocks)

    # Remove lower-confidence spans among those that overlap
    spans, dropped_spans_by_confidence = remove_overlaps_low_confidence_spans(spans)
    # Remove smaller spans among those that overlap
    spans, dropped_spans_by_span_overlap = remove_overlaps_min_spans(spans)

    # Construct spans based on parse_mode, primarily filling text-type characters
    if ocr_enable:
        pass
    else:
        # Use the new hybrid OCR scheme
        spans = txt_spans_extract(page, spans, page_pil_img, scale, all_bboxes, all_discarded_blocks)

    # Process discarded_blocks (no layout required) first
    discarded_block_with_spans, spans = fill_spans_in_blocks(
        all_discarded_blocks, spans, 0.4
    )
    fix_discarded_blocks = fix_discarded_block(discarded_block_with_spans)

    # Skip if the current page has no valid bboxes
    if len(all_bboxes) == 0 and len(fix_discarded_blocks) == 0:
        return None

    # Take screenshots of image, table, and interline_equation
    for span in spans:
        if span['type'] in [ContentType.IMAGE, ContentType.TABLE, ContentType.INTERLINE_EQUATION]:
            span = cut_image_and_table(
                span, page_pil_img, page_img_md5, page_index, image_writer, scale=scale
            )

    # Fill spans into blocks
    block_with_spans, spans = fill_spans_in_blocks(all_bboxes, spans, 0.5)

    # Perform fix operations on blocks
    fix_blocks = fix_block_spans(block_with_spans)

    # Sort blocks
    sorted_blocks = sort_blocks_by_bbox(fix_blocks, page_w, page_h, footnote_blocks)

    # Construct page_info
    page_info = make_page_info_dict(sorted_blocks, page_index, page_w, page_h, fix_discarded_blocks)

    return page_info


def result_to_middle_json(
    model_list,
    images_list,
    pdf_doc,
    image_writer,
    lang=None,
    ocr_enable=False,
    formula_enabled=True,
    ocr_engine=None,
):
    middle_json = {"pdf_info": [], "_backend":"pipeline", "_version_name": __version__}
    formula_enabled = get_formula_enable(formula_enabled)
    for page_index, page_model_info in tqdm(enumerate(model_list), total=len(model_list), desc="Processing pages"):
        page = pdf_doc[page_index]
        image_dict = images_list[page_index]
        page_info = page_model_info_to_page_info(
            page_model_info, image_dict, page, image_writer, page_index, ocr_enable=ocr_enable, formula_enabled=formula_enabled
        )
        if page_info is None:
            page_w, page_h = map(int, page.get_size())
            page_info = make_page_info_dict([], page_index, page_w, page_h, [])
        middle_json["pdf_info"].append(page_info)

    from vparse.utils.engine.processor import refine_middle_json
    return refine_middle_json(
        middle_json,
        pdf_doc=pdf_doc,
        lang=lang,
        ocr_enable=ocr_enable,
        ocr_engine=ocr_engine,
        formula_enabled=formula_enabled
    )


def make_page_info_dict(blocks, page_id, page_w, page_h, discarded_blocks):
    return_dict = {
        'preproc_blocks': blocks,
        'page_idx': page_id,
        'page_size': [page_w, page_h],
        'discarded_blocks': discarded_blocks,
    }
    return return_dict
