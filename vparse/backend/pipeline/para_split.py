# Copyright (c) Opendatalab. All rights reserved.
import copy
from loguru import logger
from vparse.utils.enum_class import ContentType, BlockType, SplitFlag
from vparse.utils.language import detect_lang


LINE_STOP_FLAG = ('.', '!', '?', '。', '！', '？', ')', '）', '"', '”', ':', '：', ';', '；')
LIST_END_FLAG = ('.', '。', ';', '；')


class ListLineTag:
    IS_LIST_START_LINE = 'is_list_start_line'
    IS_LIST_END_LINE = 'is_list_end_line'


def __process_blocks(blocks, ocr_engine=None):
    # Pre-process all blocks
    # 1. Group blocks by 'title' and 'interline_equation'
    # 2. Reset bbox boundaries based on line information

    result = []
    current_group = []

    for i in range(len(blocks)):
        current_block = blocks[i]

        # If current block is of type 'text'
        if current_block['type'] == 'text':
            current_block['bbox_fs'] = copy.deepcopy(current_block['bbox'])
            if ocr_engine != "tesseract":
                if 'lines' in current_block and len(current_block['lines']) > 0:
                    current_block['bbox_fs'] = [
                        min([line['bbox'][0] for line in current_block['lines']]),
                        min([line['bbox'][1] for line in current_block['lines']]),
                        max([line['bbox'][2] for line in current_block['lines']]),
                        max([line['bbox'][3] for line in current_block['lines']]),
                    ]
            current_group.append(current_block)

        # Check if next block exists
        if i + 1 < len(blocks):
            next_block = blocks[i + 1]
            # If next block is not 'text' and is 'title' or 'interline_equation'
            if next_block['type'] in ['title', 'interline_equation']:
                result.append(current_group)
                current_group = []

    # Handle the last group
    if current_group:
        result.append(current_group)

    return result


def __is_list_or_index_block(block):
    # A list block should satisfy the following characteristics:
    # 1. Multiple lines in block. 2. Multiple lines aligned to the left. 3. Multiple lines not aligned to the right (jagged).
    # 1. Multiple lines in block. 2. Multiple lines aligned to the left. 3. Multiple lines end with an end-flag.
    # 1. Multiple lines in block. 2. Multiple lines aligned to the left. 3. Multiple lines indented on the left.

    # index block is a special type of list block
    # An index block should satisfy the following characteristics:
    # 1. Multiple lines in block. 2. Multiple lines aligned on both sides. 3. Lines start or end with a digit.
    if len(block['lines']) >= 2:
        first_line = block['lines'][0]
        line_height = first_line['bbox'][3] - first_line['bbox'][1]
        block_weight = block['bbox_fs'][2] - block['bbox_fs'][0]
        block_height = block['bbox_fs'][3] - block['bbox_fs'][1]
        page_weight, page_height = block['page_size']

        left_close_num = 0
        left_not_close_num = 0
        right_not_close_num = 0
        right_close_num = 0
        lines_text_list = []
        center_close_num = 0
        external_sides_not_close_num = 0
        multiple_para_flag = False
        last_line = block['lines'][-1]

        if page_weight == 0:
            block_weight_radio = 0
        else:
            block_weight_radio = block_weight / page_weight
        # logger.info(f"block_weight_radio: {block_weight_radio}")

        # If the first line is not left-aligned but right-aligned, and the last line is left-aligned but not right-aligned (first line may be right-unaligned).
        if (
            first_line['bbox'][0] - block['bbox_fs'][0] > line_height / 2
            and abs(last_line['bbox'][0] - block['bbox_fs'][0]) < line_height / 2
            and block['bbox_fs'][2] - last_line['bbox'][2] > line_height
        ):
            multiple_para_flag = True

        block_text = ''

        for line in block['lines']:
            line_text = ''

            for span in line['spans']:
                span_type = span['type']
                if span_type == ContentType.TEXT:
                    line_text += span['content'].strip()
            # Add all text, including empty lines, keeping length consistent with block['lines'].
            lines_text_list.append(line_text)
            block_text = ''.join(lines_text_list)

        block_lang = detect_lang(block_text)
        # logger.info(f"block_lang: {block_lang}")

        for line in block['lines']:
            line_mid_x = (line['bbox'][0] + line['bbox'][2]) / 2
            block_mid_x = (block['bbox_fs'][0] + block['bbox_fs'][2]) / 2
            if (
                line['bbox'][0] - block['bbox_fs'][0] > 0.7 * line_height
                and block['bbox_fs'][2] - line['bbox'][2] > 0.7 * line_height
            ):
                external_sides_not_close_num += 1
            if abs(line_mid_x - block_mid_x) < line_height / 2:
                center_close_num += 1

            # Check if count of left-aligned lines > 2 (alignment threshold: abs(diff) < line_height/2).
            if abs(block['bbox_fs'][0] - line['bbox'][0]) < line_height / 2:
                left_close_num += 1
            elif line['bbox'][0] - block['bbox_fs'][0] > line_height:
                left_not_close_num += 1

            # Check if right side is aligned
            if abs(block['bbox_fs'][2] - line['bbox'][2]) < line_height:
                right_close_num += 1
            else:
                # Chinese-like languages don't have extra-long words; use a unified threshold.
                if block_lang in ['zh', 'ja', 'ko']:
                    closed_area = 0.26 * block_weight
                else:
                    # Check for gap on the right; use 0.3 * block width as a heuristic threshold.
                    # Use smaller threshold for wide blocks, larger for narrow blocks.
                    if block_weight_radio >= 0.5:
                        closed_area = 0.26 * block_weight
                    else:
                        closed_area = 0.36 * block_weight
                if block['bbox_fs'][2] - line['bbox'][2] > closed_area:
                    right_not_close_num += 1

        # Check if > 80% of lines end with LIST_END_FLAG.
        line_end_flag = False
        # Check if > 80% of lines start or end with a digit.
        line_num_flag = False
        num_start_count = 0
        num_end_count = 0
        flag_end_count = 0

        if len(lines_text_list) > 0:
            for line_text in lines_text_list:
                if len(line_text) > 0:
                    if line_text[-1] in LIST_END_FLAG:
                        flag_end_count += 1
                    if line_text[0].isdigit():
                        num_start_count += 1
                    if line_text[-1].isdigit():
                        num_end_count += 1

            if (
                num_start_count / len(lines_text_list) >= 0.8
                or num_end_count / len(lines_text_list) >= 0.8
            ):
                line_num_flag = True
            if flag_end_count / len(lines_text_list) >= 0.8:
                line_end_flag = True

        # Some tables of contents aren't right-aligned; consider as 'index' if one side is fully aligned and digit rules match.
        if (
            left_close_num / len(block['lines']) >= 0.8
            or right_close_num / len(block['lines']) >= 0.8
        ) and line_num_flag:
            for line in block['lines']:
                line[ListLineTag.IS_LIST_START_LINE] = True
            return BlockType.INDEX

        # Special list detection for centered lines: multi-line, most lines not aligned on either side, centers horizontally close.
        # Additional condition: block aspect ratio requirements.
        elif (
            external_sides_not_close_num >= 2
            and center_close_num == len(block['lines'])
            and external_sides_not_close_num / len(block['lines']) >= 0.5
            and block_height / block_weight > 0.4
        ):
            for line in block['lines']:
                line[ListLineTag.IS_LIST_START_LINE] = True
            return BlockType.LIST

        elif (
            left_close_num >= 2
            and (right_not_close_num >= 2 or line_end_flag or left_not_close_num >= 2)
            and not multiple_para_flag
            # and block_weight_radio > 0.27
        ):
            # Handle non-indented lists where all lines are left-aligned; determine item ends by right-side gaps.
            if left_close_num / len(block['lines']) > 0.8:
                # Each item is a single line, fully left-aligned (short item list).
                if flag_end_count == 0 and right_close_num / len(block['lines']) < 0.5:
                    for line in block['lines']:
                        if abs(block['bbox_fs'][0] - line['bbox'][0]) < line_height / 2:
                            line[ListLineTag.IS_LIST_START_LINE] = True
                # Most line items have end markers; use them to distinguish items.
                elif line_end_flag:
                    for i, line in enumerate(block['lines']):
                        if (
                            len(lines_text_list[i]) > 0
                            and lines_text_list[i][-1] in LIST_END_FLAG
                        ):
                            line[ListLineTag.IS_LIST_END_LINE] = True
                            if i + 1 < len(block['lines']):
                                block['lines'][i + 1][
                                    ListLineTag.IS_LIST_START_LINE
                                ] = True
                # Items lack end markers and indentation; use right-side gaps to identify item ends.
                else:
                    line_start_flag = False
                    for i, line in enumerate(block['lines']):
                        if line_start_flag:
                            line[ListLineTag.IS_LIST_START_LINE] = True
                            line_start_flag = False

                        if (
                            abs(block['bbox_fs'][2] - line['bbox'][2])
                            > 0.1 * block_weight
                        ):
                            line[ListLineTag.IS_LIST_END_LINE] = True
                            line_start_flag = True
            # Specialized ordered list with indentation: start lines indented and starting with digits; end lines end with end flags (counts must match).
            elif num_start_count >= 2 and num_start_count == flag_end_count:
                for i, line in enumerate(block['lines']):
                    if len(lines_text_list[i]) > 0:
                        if lines_text_list[i][0].isdigit():
                            line[ListLineTag.IS_LIST_START_LINE] = True
                        if lines_text_list[i][-1] in LIST_END_FLAG:
                            line[ListLineTag.IS_LIST_END_LINE] = True
            else:
                # Normal indented list processing
                for line in block['lines']:
                    if abs(block['bbox_fs'][0] - line['bbox'][0]) < line_height / 2:
                        line[ListLineTag.IS_LIST_START_LINE] = True
                    if abs(block['bbox_fs'][2] - line['bbox'][2]) > line_height:
                        line[ListLineTag.IS_LIST_END_LINE] = True

            return BlockType.LIST
        else:
            return BlockType.TEXT
    else:
        return BlockType.TEXT


def __merge_2_text_blocks(block1, block2):
    if len(block1['lines']) > 0:
        first_line = block1['lines'][0]
        line_height = first_line['bbox'][3] - first_line['bbox'][1]
        block1_weight = block1['bbox'][2] - block1['bbox'][0]
        block2_weight = block2['bbox'][2] - block2['bbox'][0]
        min_block_weight = min(block1_weight, block2_weight)
        if abs(block1['bbox_fs'][0] - first_line['bbox'][0]) < line_height / 2:
            last_line = block2['lines'][-1]
            if len(last_line['spans']) > 0:
                last_span = last_line['spans'][-1]
                line_height = last_line['bbox'][3] - last_line['bbox'][1]
                if len(first_line['spans']) > 0:
                    first_span = first_line['spans'][0]
                    if len(first_span['content']) > 0:
                        span_start_with_num = first_span['content'][0].isdigit()
                        span_start_with_big_char = first_span['content'][0].isupper()
                        if (
                            # Gap between previous block's last line right boundary and current block's right boundary <= line_height
                            abs(block2['bbox_fs'][2] - last_line['bbox'][2]) < line_height
                            # Previous block's last span does not end with a stop flag.
                            and not last_span['content'].endswith(LINE_STOP_FLAG)
                            # Do not merge if width difference exceeds 2x.
                            and abs(block1_weight - block2_weight) < min_block_weight
                            # Next block does not start with a digit
                            and not span_start_with_num
                            # Next block does not start with an uppercase letter
                            and not span_start_with_big_char
                        ):
                            if block1['page_num'] != block2['page_num']:
                                for line in block1['lines']:
                                    for span in line['spans']:
                                        span[SplitFlag.CROSS_PAGE] = True
                            block2['lines'].extend(block1['lines'])
                            block1['lines'] = []
                            block1[SplitFlag.LINES_DELETED] = True

    return block1, block2


def __merge_2_list_blocks(block1, block2):
    if block1['page_num'] != block2['page_num']:
        for line in block1['lines']:
            for span in line['spans']:
                span[SplitFlag.CROSS_PAGE] = True
    block2['lines'].extend(block1['lines'])
    block1['lines'] = []
    block1[SplitFlag.LINES_DELETED] = True

    return block1, block2


def __is_list_group(text_blocks_group):
    # Characteristics of a list group:
    # 1. Each block <= 3 lines. 2. Left boundaries are close (omitting second rule for simplicity).
    for block in text_blocks_group:
        if len(block['lines']) > 3:
            return False
    return True


def __para_merge_page(blocks, ocr_engine=None):
    page_text_blocks_groups = __process_blocks(blocks, ocr_engine=ocr_engine)
    for text_blocks_group in page_text_blocks_groups:
        if len(text_blocks_group) > 0:
            # Determine list/index type for all blocks before merging.
            for block in text_blocks_group:
                block_type = __is_list_or_index_block(block)
                block['type'] = block_type
                # logger.info(f"{block['type']}:{block}")

        if len(text_blocks_group) > 1:
            # Determine if the group is a list group before merging.
            is_list_group = __is_list_group(text_blocks_group)

            # Iterate in reverse order
            for i in range(len(text_blocks_group) - 1, -1, -1):
                current_block = text_blocks_group[i]

                # Check if a previous block exists
                if i - 1 >= 0:
                    prev_block = text_blocks_group[i - 1]

                    if (
                        current_block['type'] == 'text'
                        and prev_block['type'] == 'text'
                        and not is_list_group
                    ):
                        __merge_2_text_blocks(current_block, prev_block)
                    elif (
                        current_block['type'] == BlockType.LIST
                        and prev_block['type'] == BlockType.LIST
                    ) or (
                        current_block['type'] == BlockType.INDEX
                        and prev_block['type'] == BlockType.INDEX
                    ):
                        __merge_2_list_blocks(current_block, prev_block)

        else:
            continue


def para_split(page_info_list, ocr_engine=None):
    all_blocks = []
    for page_info in page_info_list:
        blocks = copy.deepcopy(page_info['preproc_blocks'])
        for block in blocks:
            block['page_num'] = page_info['page_idx']
            block['page_size'] = page_info['page_size']
        all_blocks.extend(blocks)

    __para_merge_page(all_blocks, ocr_engine=ocr_engine)
    for page_info in page_info_list:
        page_info['para_blocks'] = []
        for block in all_blocks:
            if 'page_num' in block:
                if block['page_num'] == page_info['page_idx']:
                    page_info['para_blocks'].append(block)
                    # Delete redundant page_num and page_size fields from block.
                    del block['page_num']
                    del block['page_size']


if __name__ == '__main__':
    input_blocks = []
    # Call function
    groups = __process_blocks(input_blocks)
    for group_index, group in enumerate(groups):
        print(f'Group {group_index}: {group}')
