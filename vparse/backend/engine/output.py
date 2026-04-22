import os
from loguru import logger

from vparse.utils.char_utils import full_to_half_exclude_marks, is_hyphen_at_line_end
from vparse.utils.config_reader import get_latex_delimiter_config, get_formula_enable, get_table_enable
from vparse.utils.enum_class import MakeMode, BlockType, ContentType, ContentTypeV2
from vparse.utils.language import detect_lang

# Import specific to pipeline backend needs
try:
    from vparse.backend.pipeline.para_split import ListLineTag
except ImportError:
    # Provide a fallback if not available
    class ListLineTag:
        IS_LIST_START_LINE = "is_list_start_line"

latex_delimiters_config = get_latex_delimiter_config()

default_delimiters = {
    'display': {'left': '$$', 'right': '$$'},
    'inline': {'left': '$', 'right': '$'}
}

delimiters = latex_delimiters_config if latex_delimiters_config else default_delimiters

display_left_delimiter = delimiters['display']['left']
display_right_delimiter = delimiters['display']['right']
inline_left_delimiter = delimiters['inline']['left']
inline_right_delimiter = delimiters['inline']['right']


def escape_special_markdown_char(content):
    """
    Escape special Markdown characters in text.
    """
    if not isinstance(content, str):
        return content
    special_chars = ["*", "`", "~", "$"]
    for char in special_chars:
        content = content.replace(char, "\\" + char)
    return content


def get_title_level(block):
    title_level = block.get('level', 1)
    if title_level > 4:
        title_level = 4
    elif title_level < 1:
        title_level = 0
    return title_level


def merge_para_with_text(para_block, formula_enable=True, img_buket_path=''):
    block_text = ''
    for line in para_block['lines']:
        for span in line['spans']:
            if span['type'] in [ContentType.TEXT]:
                span['content'] = full_to_half_exclude_marks(span['content'])
                block_text += span['content']
    block_lang = detect_lang(block_text)

    para_text = ''
    for i, line in enumerate(para_block['lines']):
        # Pipeline-specific list handling
        if i >= 1 and line.get(ListLineTag.IS_LIST_START_LINE, False):
            para_text += '  \n'

        for j, span in enumerate(line['spans']):
            span_type = span['type']
            content = ''
            if span_type == ContentType.TEXT:
                content = escape_special_markdown_char(span['content'])
            elif span_type == ContentType.INLINE_EQUATION:
                if span.get('content', ''):
                    content = f"{inline_left_delimiter}{span['content']}{inline_right_delimiter}"
            elif span_type == ContentType.INTERLINE_EQUATION:
                if formula_enable and span.get('content', ''):
                    content = f"\n{display_left_delimiter}\n{span['content']}\n{display_right_delimiter}\n"
                else:
                    if span.get('image_path', ''):
                        content = f"![]({img_buket_path}/{span['image_path']})"

            content = content.strip()
            if content:
                if span_type == ContentType.INTERLINE_EQUATION:
                    para_text += content
                    continue

                # Define CJK language set (Chinese, Japanese, Korean)
                cjk_langs = {'zh', 'ja', 'ko'}

                # Determine if it is the end-of-line span
                is_last_span = j == len(line['spans']) - 1

                if block_lang in cjk_langs:  # For CJK languages, line breaks do not need spaces
                    if is_last_span and span_type != ContentType.INLINE_EQUATION:
                        para_text += content
                    else:
                        para_text += f'{content} '
                else:
                    # In Western text context, check hyphenation
                    if span_type in [ContentType.TEXT, ContentType.INLINE_EQUATION]:
                        if (
                                is_last_span
                                and span_type == ContentType.TEXT
                                and is_hyphen_at_line_end(content)
                        ):
                            # Remove hyphen if next line starts with lowercase
                            if (
                                    i+1 < len(para_block['lines'])
                                    and para_block['lines'][i + 1].get('spans')
                                    and para_block['lines'][i + 1]['spans'][0].get('type') == ContentType.TEXT
                                    and para_block['lines'][i + 1]['spans'][0].get('content', '')
                                    and para_block['lines'][i + 1]['spans'][0]['content'][0].islower()
                            ):
                                para_text += content[:-1]
                            else:
                                para_text += content
                        else:
                            para_text += f'{content} '
    return para_text


def mk_blocks_to_markdown(para_blocks, make_mode, formula_enable, table_enable, img_buket_path=''):
    page_markdown = []
    for para_block in para_blocks:
        para_text = ''
        para_type = para_block['type']
        if para_type in [BlockType.TEXT, BlockType.INTERLINE_EQUATION, BlockType.PHONETIC, BlockType.REF_TEXT, BlockType.INDEX, BlockType.LIST]:
            # Note: For BlockType.LIST, VLM implementation iterates nested blocks, Pipeline uses merge_para directly.
            # We use a combined approach.
            if para_type == BlockType.LIST and 'blocks' in para_block:
                 for block in para_block['blocks']:
                    item_text = merge_para_with_text(block, formula_enable=formula_enable, img_buket_path=img_buket_path)
                    para_text += f"{item_text}  \n"
            else:
                para_text = merge_para_with_text(para_block, formula_enable=formula_enable, img_buket_path=img_buket_path)
        
        elif para_type == BlockType.TITLE:
            title_level = get_title_level(para_block)
            para_text = f'{"#" * title_level} {merge_para_with_text(para_block)}'
        
        elif para_type == BlockType.IMAGE:
            if make_mode == MakeMode.NLP_MD:
                continue
            elif make_mode == MakeMode.MM_MD:
                has_image_footnote = any(block['type'] == BlockType.IMAGE_FOOTNOTE for block in para_block.get('blocks', []))
                blocks = para_block.get('blocks', [])
                
                # Standardized order: Caption -> Body -> Footnote or Body -> Caption
                if has_image_footnote:
                    for block in blocks:
                        if block['type'] == BlockType.IMAGE_CAPTION:
                            para_text += merge_para_with_text(block) + '  \n'
                    for block in blocks:
                        if block['type'] == BlockType.IMAGE_BODY:
                            for line in block.get('lines', []):
                                for span in line.get('spans', []):
                                    if span['type'] == ContentType.IMAGE and span.get('image_path', ''):
                                        para_text += f"![]({img_buket_path}/{span['image_path']})"
                    for block in blocks:
                        if block['type'] == BlockType.IMAGE_FOOTNOTE:
                            para_text += '  \n' + merge_para_with_text(block)
                else:
                    for block in blocks:
                        if block['type'] == BlockType.IMAGE_BODY:
                            for line in block.get('lines', []):
                                for span in line.get('spans', []):
                                    if span['type'] == ContentType.IMAGE and span.get('image_path', ''):
                                        para_text += f"![]({img_buket_path}/{span['image_path']})"
                    for block in blocks:
                        if block['type'] == BlockType.IMAGE_CAPTION:
                            para_text += '  \n' + merge_para_with_text(block)

        elif para_type == BlockType.TABLE:
            if make_mode == MakeMode.NLP_MD:
                continue
            elif make_mode == MakeMode.MM_MD:
                blocks = para_block.get('blocks', [])
                for block in blocks:
                    if block['type'] == BlockType.TABLE_CAPTION:
                        para_text += merge_para_with_text(block) + '  \n'
                for block in blocks:
                    if block['type'] == BlockType.TABLE_BODY:
                        for line in block.get('lines', []):
                            for span in line.get('spans', []):
                                if span['type'] == ContentType.TABLE:
                                    if table_enable:
                                        if span.get('html', ''):
                                            para_text += f"\n{span['html']}\n"
                                        elif span.get('image_path', ''):
                                            para_text += f"![]({img_buket_path}/{span['image_path']})"
                                    else:
                                        if span.get('image_path', ''):
                                            para_text += f"![]({img_buket_path}/{span['image_path']})"
                for block in blocks:
                    if block['type'] == BlockType.TABLE_FOOTNOTE:
                        para_text += '\n' + merge_para_with_text(block) + '  '
        
        elif para_type == BlockType.CODE:
            sub_type = para_block.get("sub_type")
            blocks = para_block.get('blocks', [])
            for block in blocks:
                if block['type'] == BlockType.CODE_CAPTION:
                    para_text += merge_para_with_text(block) + '  \n'
            for block in blocks:
                if block['type'] == BlockType.CODE_BODY:
                    if sub_type == BlockType.CODE:
                        guess_lang = para_block.get("guess_lang", "txt")
                        para_text += f"```{guess_lang}\n{merge_para_with_text(block)}\n```"
                    elif sub_type == BlockType.ALGORITHM:
                        para_text += merge_para_with_text(block)

        if para_text.strip():
            page_markdown.append(para_text.strip())

    return page_markdown


make_blocks_to_markdown = mk_blocks_to_markdown


def make_blocks_to_content_list(para_block, img_buket_path, page_idx, page_size):
    para_type = para_block['type']
    para_content = {}
    
    # Text-like types
    text_types = [
        BlockType.TEXT, BlockType.REF_TEXT, BlockType.PHONETIC, BlockType.HEADER,
        BlockType.FOOTER, BlockType.PAGE_NUMBER, BlockType.ASIDE_TEXT, 
        BlockType.PAGE_FOOTNOTE, BlockType.INDEX, BlockType.DISCARDED
    ]
    
    if para_type in text_types:
        para_content = {
            'type': ContentType.TEXT if para_type != BlockType.DISCARDED else BlockType.DISCARDED,
            'text': merge_para_with_text(para_block),
        }
    
    elif para_type == BlockType.LIST:
        para_content = {
            'type': para_type,
            'sub_type': para_block.get('sub_type', ''),
            'list_items': [],
        }
        if 'blocks' in para_block:
            for block in para_block['blocks']:
                item_text = merge_para_with_text(block)
                if item_text.strip():
                    para_content['list_items'].append(item_text)
        else:
            # Fallback for flat list structure
            para_content['text'] = merge_para_with_text(para_block)

    elif para_type == BlockType.TITLE:
        para_content = {
            'type': ContentType.TEXT,
            'text': merge_para_with_text(para_block),
        }
        title_level = get_title_level(para_block)
        if title_level != 0:
            para_content['text_level'] = title_level

    elif para_type == BlockType.INTERLINE_EQUATION:
        img_path = ""
        if 'lines' in para_block and para_block['lines'] and para_block['lines'][0]['spans']:
            img_path = para_block['lines'][0]['spans'][0].get('image_path', '')
            
        para_content = {
            'type': ContentType.EQUATION,
            'img_path': f"{img_buket_path}/{img_path}" if img_path else "",
            'text': merge_para_with_text(para_block),
            'text_format': 'latex',
        }

    elif para_type == BlockType.IMAGE:
        para_content = {'type': ContentType.IMAGE, 'img_path': '', BlockType.IMAGE_CAPTION: [], BlockType.IMAGE_FOOTNOTE: []}
        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.IMAGE_BODY:
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        if span['type'] == ContentType.IMAGE and span.get('image_path', ''):
                            para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"
            if block['type'] == BlockType.IMAGE_CAPTION:
                para_content[BlockType.IMAGE_CAPTION].append(merge_para_with_text(block))
            if block['type'] == BlockType.IMAGE_FOOTNOTE:
                para_content[BlockType.IMAGE_FOOTNOTE].append(merge_para_with_text(block))

    elif para_type == BlockType.TABLE:
        para_content = {'type': ContentType.TABLE, 'img_path': '', BlockType.TABLE_CAPTION: [], BlockType.TABLE_FOOTNOTE: []}
        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.TABLE_BODY:
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        if span['type'] == ContentType.TABLE:
                            if span.get('html', ''):
                                para_content[BlockType.TABLE_BODY] = f"{span['html']}"
                            if span.get('image_path', ''):
                                para_content['img_path'] = f"{img_buket_path}/{span['image_path']}"
            if block['type'] == BlockType.TABLE_CAPTION:
                para_content[BlockType.TABLE_CAPTION].append(merge_para_with_text(block))
            if block['type'] == BlockType.TABLE_FOOTNOTE:
                para_content[BlockType.TABLE_FOOTNOTE].append(merge_para_with_text(block))

    elif para_type == BlockType.CODE:
        para_content = {'type': BlockType.CODE, 'sub_type': para_block.get("sub_type"), BlockType.CODE_CAPTION: []}
        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.CODE_BODY:
                para_content[BlockType.CODE_BODY] = merge_para_with_text(block)
                if para_block.get("sub_type") == BlockType.CODE:
                    para_content["guess_lang"] = para_block.get("guess_lang")
            if block['type'] == BlockType.CODE_CAPTION:
                para_content[BlockType.CODE_CAPTION].append(merge_para_with_text(block))

    if para_content:
        page_width, page_height = page_size
        para_bbox = para_block.get('bbox')
        if para_bbox:
            x0, y0, x1, y1 = para_bbox
            para_content['bbox'] = [
                int(x0 * 1000 / page_width),
                int(y0 * 1000 / page_height),
                int(x1 * 1000 / page_width),
                int(y1 * 1000 / page_height),
            ]
        para_content['page_idx'] = page_idx

    return para_content


def get_body_data(para_block):
    def get_data_from_spans(lines):
        for line in lines:
            for span in line.get('spans', []):
                span_type = span.get('type')
                if span_type == ContentType.TABLE:
                    return span.get('image_path', ''), span.get('html', '')
                elif span_type == ContentType.IMAGE:
                    return span.get('image_path', ''), ''
                elif span_type == ContentType.INTERLINE_EQUATION:
                    return span.get('image_path', ''), span.get('content', '')
                elif span_type == ContentType.TEXT:
                    return '', span.get('content', '')
        return '', ''

    if 'blocks' in para_block:
        for block in para_block['blocks']:
            block_type = block.get('type')
            if block_type in [BlockType.IMAGE_BODY, BlockType.TABLE_BODY, BlockType.CODE_BODY]:
                result = get_data_from_spans(block.get('lines', []))
                if result != ('', ''):
                    return result
    return get_data_from_spans(para_block.get('lines', []))


def merge_para_with_text_v2(para_block):
    block_text = ''
    for line in para_block['lines']:
        for span in line['spans']:
            if span['type'] in [ContentType.TEXT]:
                span['content'] = full_to_half_exclude_marks(span['content'])
                block_text += span['content']
    block_lang = detect_lang(block_text)

    para_content = []
    para_type = para_block['type']
    for i, line in enumerate(para_block['lines']):
        for j, span in enumerate(line['spans']):
            span_type = span['type']
            if span.get("content", '').strip():
                if span_type == ContentType.TEXT:
                    span_type = ContentTypeV2.SPAN_PHONETIC if para_type == BlockType.PHONETIC else ContentTypeV2.SPAN_TEXT
                if span_type == ContentType.INLINE_EQUATION:
                    span_type = ContentTypeV2.SPAN_EQUATION_INLINE
                
                if span_type == ContentTypeV2.SPAN_TEXT:
                    cjk_langs = {'zh', 'ja', 'ko'}
                    is_last_span = j == len(line['spans']) - 1

                    if block_lang in cjk_langs:
                        span_content = span['content'] if is_last_span else f"{span['content']} "
                    else:
                        if is_last_span and is_hyphen_at_line_end(span['content']):
                            if (
                                    i + 1 < len(para_block['lines'])
                                    and para_block['lines'][i + 1].get('spans')
                                    and para_block['lines'][i + 1]['spans'][0].get('type') == ContentType.TEXT
                                    and para_block['lines'][i + 1]['spans'][0].get('content', '')
                                    and para_block['lines'][i + 1]['spans'][0]['content'][0].islower()
                            ):
                                span_content = span['content'][:-1]
                            else:
                                span_content = span['content']
                        else:
                            span_content = f"{span['content']} "

                    if para_content and para_content[-1]['type'] == span_type:
                        para_content[-1]['content'] += span_content
                    else:
                        para_content.append({'type': span_type, 'content': span_content})
                
                elif span_type in [ContentTypeV2.SPAN_PHONETIC, ContentTypeV2.SPAN_EQUATION_INLINE]:
                    para_content.append({'type': span_type, 'content': span['content']})
    return para_content


def make_blocks_to_content_list_v2(para_block, img_buket_path, page_size):
    para_type = para_block['type']
    para_content = {}
    
    type_map = {
        BlockType.HEADER: ContentTypeV2.PAGE_HEADER,
        BlockType.FOOTER: ContentTypeV2.PAGE_FOOTER,
        BlockType.ASIDE_TEXT: ContentTypeV2.PAGE_ASIDE_TEXT,
        BlockType.PAGE_NUMBER: ContentTypeV2.PAGE_NUMBER,
        BlockType.PAGE_FOOTNOTE: ContentTypeV2.PAGE_FOOTNOTE,
    }
    
    if para_type in type_map:
        content_type = type_map[para_type]
        para_content = {
            'type': content_type,
            'content': {f"{content_type}_content": merge_para_with_text_v2(para_block)}
        }
    elif para_type == BlockType.TITLE:
        title_level = get_title_level(para_block)
        if title_level != 0:
            para_content = {
                'type': ContentTypeV2.TITLE,
                'content': {"title_content": merge_para_with_text_v2(para_block), "level": title_level}
            }
        else:
            para_content = {
                'type': ContentTypeV2.PARAGRAPH,
                'content': {"paragraph_content": merge_para_with_text_v2(para_block)}
            }
    elif para_type in [BlockType.TEXT, BlockType.PHONETIC]:
        para_content = {
            'type': ContentTypeV2.PARAGRAPH,
            'content': {'paragraph_content': merge_para_with_text_v2(para_block)}
        }
    elif para_type == BlockType.INTERLINE_EQUATION:
        image_path, math_content = get_body_data(para_block)
        para_content = {
            'type': ContentTypeV2.EQUATION_INTERLINE,
            'content': {
                'math_content': math_content,
                'math_type': 'latex',
                'image_source': {'path': f"{img_buket_path}/{image_path}"},
            }
        }
    elif para_type == BlockType.IMAGE:
        image_caption = []
        image_footnote = []
        image_path, _ = get_body_data(para_block)
        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.IMAGE_CAPTION:
                image_caption.extend(merge_para_with_text_v2(block))
            if block['type'] == BlockType.IMAGE_FOOTNOTE:
                image_footnote.extend(merge_para_with_text_v2(block))
        para_content = {
            'type': ContentTypeV2.IMAGE,
            'content': {
                'image_source': {'path': f"{img_buket_path}/{image_path}"},
                'image_caption': image_caption,
                'image_footnote': image_footnote,
            }
        }
    elif para_type == BlockType.TABLE:
        table_caption = []
        table_footnote = []
        image_path, html = get_body_data(para_block)
        table_nest_level = 2 if html.count("<table") > 1 else 1
        table_type = ContentTypeV2.TABLE_COMPLEX if ("colspan" in html or "rowspan" in html or table_nest_level > 1) else ContentTypeV2.TABLE_SIMPLE

        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.TABLE_CAPTION:
                table_caption.extend(merge_para_with_text_v2(block))
            if block['type'] == BlockType.TABLE_FOOTNOTE:
                table_footnote.extend(merge_para_with_text_v2(block))
        para_content = {
            'type': ContentTypeV2.TABLE,
            'content': {
                'image_source': {'path': f"{img_buket_path}/{image_path}"},
                'table_caption': table_caption,
                'table_footnote': table_footnote,
                'html': html,
                'table_type': table_type,
                'table_nest_level': table_nest_level,
            }
        }
    elif para_type == BlockType.CODE:
        code_caption = []
        code_content = []
        for block in para_block.get('blocks', []):
            if block['type'] == BlockType.CODE_CAPTION:
                code_caption.extend(merge_para_with_text_v2(block))
            if block['type'] == BlockType.CODE_BODY:
                code_content = merge_para_with_text_v2(block)
        sub_type = para_block.get("sub_type")
        if sub_type == BlockType.CODE:
            para_content = {
                'type': ContentTypeV2.CODE,
                'content': {
                    'code_caption': code_caption,
                    'code_content': code_content,
                    'code_language': para_block.get('guess_lang', 'txt'),
                }
            }
        elif sub_type == BlockType.ALGORITHM:
            para_content = {
                'type': ContentTypeV2.ALGORITHM,
                'content': {'algorithm_caption': code_caption, 'algorithm_content': code_content}
            }
    elif para_type == BlockType.REF_TEXT:
        para_content = {
            'type': ContentTypeV2.LIST,
            'content': {
                'list_type': ContentTypeV2.LIST_REF,
                'list_items': [{'item_type': 'text', 'item_content': merge_para_with_text_v2(para_block)}],
            }
        }
    elif para_type == BlockType.LIST:
        list_type = ContentTypeV2.LIST_REF if para_block.get('sub_type') == BlockType.REF_TEXT else ContentTypeV2.LIST_TEXT
        list_items = []
        for block in para_block.get('blocks', []):
            item_content = merge_para_with_text_v2(block)
            if item_content:
                list_items.append({'item_type': 'text', 'item_content': item_content})
        para_content = {
            'type': ContentTypeV2.LIST,
            'content': {'list_type': list_type, 'list_items': list_items}
        }

    para_bbox = para_block.get('bbox')
    if para_bbox:
        page_width, page_height = page_size
        x0, y0, x1, y1 = para_bbox
        para_content['bbox'] = [int(x0 * 1000 / page_width), int(y0 * 1000 / page_height), int(x1 * 1000 / page_width), int(y1 * 1000 / page_height)]

    return para_content


def union_make(pdf_info_dict: list,
               make_mode: str,
               img_buket_path: str = '',
               ):

    formula_enable = get_formula_enable(os.getenv('VPARSE_VLM_FORMULA_ENABLE', 'True').lower() == 'true')
    table_enable = get_table_enable(os.getenv('VPARSE_VLM_TABLE_ENABLE', 'True').lower() == 'true')

    output_content = []
    for page_info in pdf_info_dict:
        paras_of_layout = page_info.get('para_blocks')
        paras_of_discarded = page_info.get('discarded_blocks')
        page_idx = page_info.get('page_idx')
        page_size = page_info.get('page_size')
        if make_mode in [MakeMode.MM_MD, MakeMode.NLP_MD]:
            if not paras_of_layout:
                continue
            # Use the unified markdown generator
            page_markdown = mk_blocks_to_markdown(paras_of_layout, make_mode, formula_enable, table_enable, img_buket_path)
            output_content.extend(page_markdown)
        elif make_mode == MakeMode.CONTENT_LIST:
            para_blocks = (paras_of_layout or []) + (paras_of_discarded or [])
            if not para_blocks:
                continue
            for para_block in para_blocks:
                para_content = make_blocks_to_content_list(para_block, img_buket_path, page_idx, page_size)
                if para_content:
                    output_content.append(para_content)
        elif make_mode == MakeMode.CONTENT_LIST_V2:
            para_blocks = (paras_of_layout or []) + (paras_of_discarded or [])
            page_contents = []
            if para_blocks:
                for para_block in para_blocks:
                    para_content = make_blocks_to_content_list_v2(para_block, img_buket_path, page_size)
                    page_contents.append(para_content)
            output_content.append(page_contents)

    if make_mode in [MakeMode.MM_MD, MakeMode.NLP_MD]:
        return '\n\n'.join(output_content)
    elif make_mode in [MakeMode.CONTENT_LIST, MakeMode.CONTENT_LIST_V2]:
        return output_content
    return None
