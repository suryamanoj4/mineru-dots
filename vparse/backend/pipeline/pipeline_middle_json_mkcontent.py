# Copyright (c) Opendatalab. All rights reserved.
from vparse.backend.engine.output import (
    union_make,
    make_blocks_to_markdown,
    make_blocks_to_content_list,
    get_title_level,
    escape_special_markdown_char,
    merge_para_with_text
)
# Re-alias mk_blocks_to_markdown if needed by any legacy calls
from vparse.backend.engine.output import mk_blocks_to_markdown as make_blocks_to_markdown_v2
