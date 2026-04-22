import os
import time
from loguru import logger
from tqdm import tqdm

from vparse.backend.utils import cross_page_table_merge
from vparse.utils.config_reader import get_device, get_llm_aided_config, get_table_enable
from vparse.utils.llm_aided import llm_aided_title
from vparse.utils.model_utils import clean_memory
from vparse.utils.ocr_utils import OcrConfidence

# Import backend-specific refinement logic
try:
    from vparse.backend.pipeline.para_split import para_split
    from vparse.backend.pipeline.model_init import AtomModelSingleton
    HAS_PIPELINE_REFINEMENT = True
except ImportError:
    HAS_PIPELINE_REFINEMENT = False

def refine_middle_json(
    middle_json,
    pdf_doc=None,
    lang=None,
    ocr_enable=False,
    ocr_engine=None,
    formula_enabled=True,
    table_enable=True
):
    """
    Unified refinement engine (Post-Processing).
    Applies OCR refinement, paragraph splitting, table merging, and title optimization.
    """
    pdf_info = middle_json.get("pdf_info", [])
    if not pdf_info:
        return middle_json

    # 1. Post-process OCR (Second pass for low-confidence text - primarily for Pipeline/Lite)
    if ocr_enable and HAS_PIPELINE_REFINEMENT:
        _apply_ocr_refinement(pdf_info, lang, ocr_engine)

    # 2. Paragraph splitting
    if HAS_PIPELINE_REFINEMENT:
        para_split(pdf_info, ocr_engine=ocr_engine)

    # 3. Merge tables across pages
    if table_enable:
        cross_page_table_merge(pdf_info)

    # 4. LLM-aided Title Optimization
    llm_aided_config = get_llm_aided_config()
    if llm_aided_config is not None:
        title_aided_config = llm_aided_config.get('title_aided', None)
        if title_aided_config is not None and title_aided_config.get('enable', False):
            llm_aided_title_start_time = time.time()
            llm_aided_title(pdf_info, title_aided_config)
            logger.info(f'llm aided title time: {round(time.time() - llm_aided_title_start_time, 2)}')

    # 5. Resource Cleanup
    if pdf_doc:
        pdf_doc.close()
    
    if os.getenv('VPARSE_DONOT_CLEAN_MEM') is None:
        # Clean memory if we processed a significant amount of data or explicitly asked
        clean_memory(get_device())

    return middle_json


def _apply_ocr_refinement(pdf_info, lang, ocr_engine):
    """Internal helper to apply second-pass OCR to low-confidence blocks."""
    need_ocr_list = []
    img_crop_list = []
    text_block_list = []
    
    for page_info in pdf_info:
        for block in page_info.get('preproc_blocks', []):
            if block['type'] in ['table', 'image']:
                for sub_block in block.get('blocks', []):
                    if sub_block['type'] in ['image_caption', 'image_footnote', 'table_caption', 'table_footnote']:
                        text_block_list.append(sub_block)
            elif block['type'] in ['text', 'title']:
                text_block_list.append(block)
        for block in page_info.get('discarded_blocks', []):
            text_block_list.append(block)
            
    for block in text_block_list:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                if 'np_img' in span:
                    need_ocr_list.append(span)
                    img_crop_list.append(span['np_img'])
                    span.pop('np_img')
                    
    if len(img_crop_list) > 0:
        atom_model_manager = AtomModelSingleton()
        ocr_model = atom_model_manager.get_atom_model(
            atom_model_name='ocr',
            det_db_box_thresh=0.3,
            lang=lang,
            ocr_engine=ocr_engine,
        )
        ocr_res_list = ocr_model.ocr(img_crop_list, det=False, tqdm_enable=True)[0]
        for index, span in enumerate(need_ocr_list):
            ocr_text, ocr_score = ocr_res_list[index]
            if ocr_score > OcrConfidence.min_confidence:
                span['content'] = ocr_text
                span['score'] = float(f"{ocr_score:.3f}")
            else:
                span['content'] = ''
                span['score'] = 0.0
