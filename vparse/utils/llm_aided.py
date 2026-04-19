# Copyright (c) Opendatalab. All rights reserved.
from loguru import logger
from openai import OpenAI
import json_repair

from vparse.backend.pipeline.pipeline_middle_json_mkcontent import merge_para_with_text


def llm_aided_title(page_info_list, title_aided_config):
    client = OpenAI(
        api_key=title_aided_config["api_key"],
        base_url=title_aided_config["base_url"],
    )
    title_dict = {}
    origin_title_list = []
    i = 0
    for page_info in page_info_list:
        blocks = page_info["para_blocks"]
        for block in blocks:
            if block["type"] == "title":
                origin_title_list.append(block)
                title_text = merge_para_with_text(block)

                if 'line_avg_height' in block:
                    line_avg_height = block['line_avg_height']
                else:
                    title_block_line_height_list = []
                    for line in block['lines']:
                        bbox = line['bbox']
                        title_block_line_height_list.append(int(bbox[3] - bbox[1]))
                    if len(title_block_line_height_list) > 0:
                        line_avg_height = sum(title_block_line_height_list) / len(title_block_line_height_list)
                    else:
                        line_avg_height = int(block['bbox'][3] - block['bbox'][1])

                title_dict[f"{i}"] = [title_text, line_avg_height, int(page_info['page_idx']) + 1]
                i += 1
    # logger.info(f"Title list: {title_dict}")

    title_optimize_prompt = f"""The input content is a dictionary of all titles from a document. Please optimize the title results according to the following guidelines to ensure they conform to a normal document hierarchy:

1. Each value in the dictionary is a list containing the following elements:
    - Title text
    - Text line height (average line height of the block containing the title)
    - Page number where the title is located

2. Preserve original content:
    - All elements in the input dictionary are valid; do not delete any elements.
    - Ensure the number of elements in the output dictionary matches the input.

3. Keep the key-value mapping within the dictionary unchanged.

4. Optimize hierarchy:
    - Assign appropriate hierarchy levels to each title element based on its semantic content.
    - Titles with larger line heights are generally higher-level titles.
    - Hierarchy levels must be continuous from beginning to end, with no skipped levels.
    - Maximum of 4 hierarchy levels; avoid excessive nesting.
    - Optimized output should only contain the integer representing the hierarchy level for each title, with no other information.

5. Consistency check and fine-tuning:
    - After initial leveling, carefully review the results for consistency.
    - Fine-tune any inconsistent levels based on context and logical order.
    - Ensure the final hierarchy reflects the document's actual structure and logic.

IMPORTANT: 
Return only the optimized dictionary of hierarchy levels in the format {{title_id: hierarchy_level}}, as shown below:
{{
  0:1,
  1:2,
  2:2,
  3:3
}}
No formatting or additional information is required.

Input title list:
{title_dict}

Corrected title list:
"""
    #5.
    #- The dictionary may contain body text misidentified as titles; you can exclude them by marking their level as 0.

    retry_count = 0
    max_retries = 3
    dict_completion = None

    # Build API call parameters
    api_params = {
        "model": title_aided_config["model"],
        "messages": [{'role': 'user', 'content': title_optimize_prompt}],
        "temperature": 0.7,
        "stream": True,
    }

    # Only add extra_body when explicitly specified in config
    if "enable_thinking" in title_aided_config:
        api_params["extra_body"] = {"enable_thinking": title_aided_config["enable_thinking"]}

    while retry_count < max_retries:
        try:
            completion = client.chat.completions.create(**api_params)
            content_pieces = []
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    content_pieces.append(chunk.choices[0].delta.content)
            content = "".join(content_pieces).strip()
            # logger.info(f"Title completion: {content}")
            if "</think>" in content:
                idx = content.index("</think>") + len("</think>")
                content = content[idx:].strip()
            dict_completion = json_repair.loads(content)
            dict_completion = {int(k): int(v) for k, v in dict_completion.items()}

            # logger.info(f"len(dict_completion): {len(dict_completion)}, len(title_dict): {len(title_dict)}")
            if len(dict_completion) == len(title_dict):
                for i, origin_title_block in enumerate(origin_title_list):
                    origin_title_block["level"] = int(dict_completion[i])
                break
            else:
                logger.warning(
                    "The number of titles in the optimized result is not equal to the number of titles in the input.")
                retry_count += 1
        except Exception as e:
            logger.exception(e)
            retry_count += 1

    if dict_completion is None:
        logger.error("Failed to decode dict after maximum retries.")
