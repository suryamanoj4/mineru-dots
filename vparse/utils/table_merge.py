# Copyright (c) Opendatalab. All rights reserved.
from copy import deepcopy

from loguru import logger
from bs4 import BeautifulSoup

from vparse.backend.vlm.vlm_middle_json_mkcontent import merge_para_with_text
from vparse.utils.char_utils import full_to_half
from vparse.utils.enum_class import BlockType, SplitFlag


CONTINUATION_END_MARKERS = [
    "(续)",
    "(续表)",
    "(续上表)",
    "(continued)",
    "(cont.)",
    "(cont’d)",
    "(…continued)",
    "续表",
]

CONTINUATION_INLINE_MARKERS = [
    "(continued)",
]


def calculate_table_total_columns(soup):
    """Calculate total columns of the table, handling rowspan and colspan by analyzing the structure

    Args:
        soup: BeautifulSoup parsed table

    Returns:
        int: Total number of columns
    """
    rows = soup.find_all("tr")
    if not rows:
        return 0

    # Create a matrix to track occupancy of each position
    max_cols = 0
    occupied = {}  # {row_idx: {col_idx: True}}

    for row_idx, row in enumerate(rows):
        col_idx = 0
        cells = row.find_all(["td", "th"])

        if row_idx not in occupied:
            occupied[row_idx] = {}

        for cell in cells:
            # Find the next unoccupied column position
            while col_idx in occupied[row_idx]:
                col_idx += 1

            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # Mark all positions occupied by this cell
            for r in range(row_idx, row_idx + rowspan):
                if r not in occupied:
                    occupied[r] = {}
                for c in range(col_idx, col_idx + colspan):
                    occupied[r][c] = True

            col_idx += colspan
            max_cols = max(max_cols, col_idx)

    return max_cols


def build_table_occupied_matrix(soup):
    """Build table occupancy matrix, returning effective columns per row

    Args:
        soup: BeautifulSoup parsed table

    Returns:
        dict: {row_idx: effective_columns} effective columns per row (considering rowspan)
    """
    rows = soup.find_all("tr")
    if not rows:
        return {}

    occupied = {}  # {row_idx: {col_idx: True}}
    row_effective_cols = {}  # {row_idx: effective_columns}

    for row_idx, row in enumerate(rows):
        col_idx = 0
        cells = row.find_all(["td", "th"])

        if row_idx not in occupied:
            occupied[row_idx] = {}

        for cell in cells:
            # Find the next unoccupied column position
            while col_idx in occupied[row_idx]:
                col_idx += 1

            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # Mark all positions occupied by this cell
            for r in range(row_idx, row_idx + rowspan):
                if r not in occupied:
                    occupied[r] = {}
                for c in range(col_idx, col_idx + colspan):
                    occupied[r][c] = True

            col_idx += colspan

        # Effective columns for this row is the max occupied column index + 1
        if occupied[row_idx]:
            row_effective_cols[row_idx] = max(occupied[row_idx].keys()) + 1
        else:
            row_effective_cols[row_idx] = 0

    return row_effective_cols


def calculate_row_effective_columns(soup, row_idx):
    """Calculate effective columns for a specific row (considering rowspan)

    Args:
        soup: BeautifulSoup parsed table
        row_idx: Row index

    Returns:
        int: Effective columns for the row
    """
    row_effective_cols = build_table_occupied_matrix(soup)
    return row_effective_cols.get(row_idx, 0)


def calculate_row_columns(row):
    """
    Calculate actual columns of a table row, considering colspan

    Args:
        row: BeautifulSoup tr element object

    Returns:
        int: Actual columns of the row
    """
    cells = row.find_all(["td", "th"])
    column_count = 0

    for cell in cells:
        colspan = int(cell.get("colspan", 1))
        column_count += colspan

    return column_count


def calculate_visual_columns(row):
    """
    Calculate visual columns of a table row (number of td/th cells, ignoring colspan)

    Args:
        row: BeautifulSoup tr element object

    Returns:
        int: Visual columns of the row (actual cell count)
    """
    cells = row.find_all(["td", "th"])
    return len(cells)


def detect_table_headers(soup1, soup2, max_header_rows=5):
    """
    Detect and compare headers of two tables

    Args:
        soup1: BeautifulSoup object for the first table
        soup2: BeautifulSoup object for the second table
        max_header_rows: Maximum possible header rows

    Returns:
        tuple: (header row count, consistency, header text list)
    """
    rows1 = soup1.find_all("tr")
    rows2 = soup2.find_all("tr")

    # Build effective column matrices for both tables
    effective_cols1 = build_table_occupied_matrix(soup1)
    effective_cols2 = build_table_occupied_matrix(soup2)

    min_rows = min(len(rows1), len(rows2), max_header_rows)
    header_rows = 0
    headers_match = True
    header_texts = []

    for i in range(min_rows):
        # Extract all cells of the current row
        cells1 = rows1[i].find_all(["td", "th"])
        cells2 = rows2[i].find_all(["td", "th"])

        # Check if structure and content of both rows are consistent
        structure_match = True

        # First check cell count
        if len(cells1) != len(cells2):
            structure_match = False
        else:
            # Check if effective columns are consistent (considering rowspan)
            if effective_cols1.get(i, 0) != effective_cols2.get(i, 0):
                structure_match = False
            else:
                # Then check cell properties and content
                for cell1, cell2 in zip(cells1, cells2):
                    colspan1 = int(cell1.get("colspan", 1))
                    rowspan1 = int(cell1.get("rowspan", 1))
                    colspan2 = int(cell2.get("colspan", 1))
                    rowspan2 = int(cell2.get("rowspan", 1))

                    # Remove all whitespace (spaces, newlines, tabs, etc.)
                    text1 = ''.join(full_to_half(cell1.get_text()).split())
                    text2 = ''.join(full_to_half(cell2.get_text()).split())

                    if colspan1 != colspan2 or rowspan1 != rowspan2 or text1 != text2:
                        structure_match = False
                        break

        if structure_match:
            header_rows += 1
            row_texts = [full_to_half(cell.get_text().strip()) for cell in cells1]
            header_texts.append(row_texts)  # Add header text
        else:
            headers_match = header_rows > 0  # Header match requires at least one row to match
            break

    # If strict match fails, try visual consistency match (only compare text content)
    if header_rows == 0:
        header_rows, headers_match, header_texts = _detect_table_headers_visual(soup1, soup2, rows1, rows2, max_header_rows)

    return header_rows, headers_match, header_texts


def _detect_table_headers_visual(soup1, soup2, rows1, rows2, max_header_rows=5):
    """
    Detect table headers based on visual consistency (compare text only, ignore colspan/rowspan differences)

    Args:
        soup1: BeautifulSoup object for the first table
        soup2: BeautifulSoup object for the second table
        rows1: Row list of the first table
        rows2: Row list of the second table
        max_header_rows: Maximum possible header rows

    Returns:
        tuple: (header row count, consistency, header text list)
    """
    # Build effective column matrices for both tables
    effective_cols1 = build_table_occupied_matrix(soup1)
    effective_cols2 = build_table_occupied_matrix(soup2)

    min_rows = min(len(rows1), len(rows2), max_header_rows)
    header_rows = 0
    headers_match = True
    header_texts = []

    for i in range(min_rows):
        cells1 = rows1[i].find_all(["td", "th"])
        cells2 = rows2[i].find_all(["td", "th"])

        # Extract text content list for each row (removing whitespace)
        texts1 = [''.join(full_to_half(cell.get_text()).split()) for cell in cells1]
        texts2 = [''.join(full_to_half(cell.get_text()).split()) for cell in cells2]

        # Check visual consistency: text content exactly the same, and effective columns consistent
        effective_cols_match = effective_cols1.get(i, 0) == effective_cols2.get(i, 0)
        if texts1 == texts2 and effective_cols_match:
            header_rows += 1
            row_texts = [full_to_half(cell.get_text().strip()) for cell in cells1]
            header_texts.append(row_texts)
        else:
            headers_match = header_rows > 0
            break

    if header_rows == 0:
        headers_match = False

    return header_rows, headers_match, header_texts


def can_merge_tables(current_table_block, previous_table_block):
    """Determine if two tables can be merged"""
    # Check if tables have captions and footnotes
    # Count footnotes in previous_table_block
    footnote_count = sum(1 for block in previous_table_block["blocks"] if block["type"] == BlockType.TABLE_FOOTNOTE)
    # If there are TABLE_CAPTION blocks, check if at least one ends with a continuation marker
    caption_blocks = [block for block in current_table_block["blocks"] if block["type"] == BlockType.TABLE_CAPTION]
    if caption_blocks:
        # Check if at least one caption contains a continuation marker
        has_continuation_marker = False
        for block in caption_blocks:
            caption_text = full_to_half(merge_para_with_text(block).strip()).lower()
            if (
                    any(caption_text.endswith(marker.lower()) for marker in CONTINUATION_END_MARKERS)
                    or any(marker.lower() in caption_text for marker in CONTINUATION_INLINE_MARKERS)
            ):
                has_continuation_marker = True
                break

        # If no caption contains a continuation marker, merging is not allowed
        if not has_continuation_marker:
            return False, None, None, None, None

        # If current_table_block caption has continuation marker, allow previous_table_block to have at most one footnote
        if footnote_count > 1:
            return False, None, None, None, None
    else:
        if footnote_count > 0:
            return False, None, None, None, None

    # Get HTML content of both tables
    current_html = ""
    previous_html = ""

    for block in current_table_block["blocks"]:
        if (block["type"] == BlockType.TABLE_BODY and block["lines"] and block["lines"][0]["spans"]):
            current_html = block["lines"][0]["spans"][0].get("html", "")

    for block in previous_table_block["blocks"]:
        if (block["type"] == BlockType.TABLE_BODY and block["lines"] and block["lines"][0]["spans"]):
            previous_html = block["lines"][0]["spans"][0].get("html", "")

    if not current_html or not previous_html:
        return False, None, None, None, None

    # Check table width difference
    x0_t1, y0_t1, x1_t1, y1_t1 = current_table_block["bbox"]
    x0_t2, y0_t2, x1_t2, y1_t2 = previous_table_block["bbox"]
    table1_width = x1_t1 - x0_t1
    table2_width = x1_t2 - x0_t2

    if abs(table1_width - table2_width) / min(table1_width, table2_width) >= 0.1:
        return False, None, None, None, None

    # Parse HTML and check table structure
    soup1 = BeautifulSoup(previous_html, "html.parser")
    soup2 = BeautifulSoup(current_html, "html.parser")

    # Check overall column count match
    table_cols1 = calculate_table_total_columns(soup1)
    table_cols2 = calculate_table_total_columns(soup2)
    # logger.debug(f"Table columns - Previous: {table_cols1}, Current: {table_cols2}")
    tables_match = table_cols1 == table_cols2

    # Check first/last row column match
    rows_match = check_rows_match(soup1, soup2)

    return (tables_match or rows_match), soup1, soup2, current_html, previous_html


def check_rows_match(soup1, soup2):
    """Check if table rows match"""
    rows1 = soup1.find_all("tr")
    rows2 = soup2.find_all("tr")

    if not (rows1 and rows2):
        return False

    # Get last data row index of the first table
    last_row_idx = None
    last_row = None
    for idx in range(len(rows1) - 1, -1, -1):
        if rows1[idx].find_all(["td", "th"]):
            last_row_idx = idx
            last_row = rows1[idx]
            break

    # Detect header row count to get the first data row of the second table
    header_count, _, _ = detect_table_headers(soup1, soup2)

    # Get first data row of the second table
    first_data_row_idx = None
    first_data_row = None
    if len(rows2) > header_count:
        first_data_row_idx = header_count
        first_data_row = rows2[header_count]  # First non-header row

    if not (last_row and first_data_row):
        return False

    # Calculate effective columns (considering rowspan and colspan)
    last_row_effective_cols = calculate_row_effective_columns(soup1, last_row_idx)
    first_row_effective_cols = calculate_row_effective_columns(soup2, first_data_row_idx)

    # Calculate actual columns (considering colspan) and visual columns
    last_row_cols = calculate_row_columns(last_row)
    first_row_cols = calculate_row_columns(first_data_row)
    last_row_visual_cols = calculate_visual_columns(last_row)
    first_row_visual_cols = calculate_visual_columns(first_data_row)

    # logger.debug(f"Row/Column count - Last row of previous table: {last_row_cols}(effective:{last_row_effective_cols}, visual:{last_row_visual_cols}), current first row: {first_row_cols}(effective:{first_row_effective_cols}, visual:{first_row_visual_cols})")

    # Consider effective columns, actual columns, and visual columns together
    return (last_row_effective_cols == first_row_effective_cols or
            last_row_cols == first_row_cols or
            last_row_visual_cols == first_row_visual_cols)


def check_row_columns_match(row1, row2):
    # Detect if colspan property is consistent cell by cell
    cells1 = row1.find_all(["td", "th"])
    cells2 = row2.find_all(["td", "th"])
    if len(cells1) != len(cells2):
        return False
    for cell1, cell2 in zip(cells1, cells2):
        colspan1 = int(cell1.get("colspan", 1))
        colspan2 = int(cell2.get("colspan", 1))
        if colspan1 != colspan2:
            return False
    return True


def adjust_table_rows_colspan(soup, rows, start_idx, end_idx,
                              reference_structure, reference_visual_cols,
                              target_cols, current_cols, reference_row):
    """Adjust colspan of table rows to match target columns

    Args:
        soup: BeautifulSoup parsed table object (for effective column calculation)
        rows: Table row list
        start_idx: Start row index
        end_idx: End row index (exclusive)
        reference_structure: Reference row colspan structure list
        reference_visual_cols: Visual columns of reference row
        target_cols: Target total columns
        current_cols: Current total columns
        reference_row: Reference row object
    """
    reference_row_copy = deepcopy(reference_row)

    # Build effective columns matrix
    effective_cols_matrix = build_table_occupied_matrix(soup)

    for i in range(start_idx, end_idx):
        row = rows[i]
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # Determine if adjustment is needed based on effective columns (considering rowspan)
        current_row_effective_cols = effective_cols_matrix.get(i, 0)
        current_row_cols = calculate_row_columns(row)

        # Skip if effective or actual columns have reached the target
        if current_row_effective_cols >= target_cols or current_row_cols >= target_cols:
            continue

        # Check if it matches the reference row structure
        if calculate_visual_columns(row) == reference_visual_cols and check_row_columns_match(row, reference_row_copy):
            # Try to apply reference structure
            if len(cells) <= len(reference_structure):
                for j, cell in enumerate(cells):
                    if j < len(reference_structure) and reference_structure[j] > 1:
                        cell["colspan"] = str(reference_structure[j])
        else:
            # Extend the last cell to fill the column count gap
            # Use effective columns to calculate difference
            cols_diff = target_cols - current_row_effective_cols
            if cols_diff > 0:
                last_cell = cells[-1]
                current_last_span = int(last_cell.get("colspan", 1))
                last_cell["colspan"] = str(current_last_span + cols_diff)


def perform_table_merge(soup1, soup2, previous_table_block, wait_merge_table_footnotes):
    """Perform table merge operation"""
    # Detect header row count and verify header consistency
    header_count, headers_match, header_texts = detect_table_headers(soup1, soup2)
    # logger.debug(f"Detected header rows: {header_count}, header match: {headers_match}")
    # logger.debug(f"Header content: {header_texts}")

    # Find tbody of the first table, fallback to table element
    tbody1 = soup1.find("tbody") or soup1.find("table")

    # Get all rows from table 1 and table 2
    rows1 = soup1.find_all("tr")
    rows2 = soup2.find_all("tr")


    if rows1 and rows2 and header_count < len(rows2):
        # Get last row of table 1 and first data row of table 2
        last_row1 = rows1[-1]
        first_data_row2 = rows2[header_count]

        # Calculate total table columns
        table_cols1 = calculate_table_total_columns(soup1)
        table_cols2 = calculate_table_total_columns(soup2)
        if table_cols1 >= table_cols2:
            reference_structure = [int(cell.get("colspan", 1)) for cell in last_row1.find_all(["td", "th"])]
            reference_visual_cols = calculate_visual_columns(last_row1)
            # Adjust table 2 rows using table 1 last row as reference
            adjust_table_rows_colspan(
                soup2, rows2, header_count, len(rows2),
                reference_structure, reference_visual_cols,
                table_cols1, table_cols2, first_data_row2
            )

        else:  # table_cols2 > table_cols1
            reference_structure = [int(cell.get("colspan", 1)) for cell in first_data_row2.find_all(["td", "th"])]
            reference_visual_cols = calculate_visual_columns(first_data_row2)
            # Adjust table 1 rows using table 2 first data row as reference
            adjust_table_rows_colspan(
                soup1, rows1, 0, len(rows1),
                reference_structure, reference_visual_cols,
                table_cols2, table_cols1, last_row1
            )

    # Append table 2 rows to table 1
    if tbody1:
        tbody2 = soup2.find("tbody") or soup2.find("table")
        if tbody2:
            # Append table 2 rows (skipping header) to table 1
            for row in rows2[header_count:]:
                row.extract()
                tbody1.append(row)

    # Clear footnotes of previous_table_block
    previous_table_block["blocks"] = [
        block for block in previous_table_block["blocks"]
        if block["type"] != BlockType.TABLE_FOOTNOTE
    ]
    # Add footnotes of pending merge table to the previous table
    for table_footnote in wait_merge_table_footnotes:
        temp_table_footnote = table_footnote.copy()
        temp_table_footnote[SplitFlag.CROSS_PAGE] = True
        previous_table_block["blocks"].append(temp_table_footnote)

    return str(soup1)


def merge_table(page_info_list):
    """Merge cross-page tables"""
    # Iterate through pages in reverse order
    for page_idx in range(len(page_info_list) - 1, -1, -1):
        # Skip the first page as it has no predecessor
        if page_idx == 0:
            continue

        page_info = page_info_list[page_idx]
        previous_page_info = page_info_list[page_idx - 1]

        # Check if current page has a table block
        if not (page_info["para_blocks"] and page_info["para_blocks"][0]["type"] == BlockType.TABLE):
            continue

        current_table_block = page_info["para_blocks"][0]

        # Check if previous page has a table block
        if not (previous_page_info["para_blocks"] and previous_page_info["para_blocks"][-1]["type"] == BlockType.TABLE):
            continue

        previous_table_block = previous_page_info["para_blocks"][-1]

        # Collect footnotes of the table pending merge
        wait_merge_table_footnotes = [
            block for block in current_table_block["blocks"]
            if block["type"] == BlockType.TABLE_FOOTNOTE
        ]

        # Check if two tables can be merged
        can_merge, soup1, soup2, current_html, previous_html = can_merge_tables(
            current_table_block, previous_table_block
        )

        if not can_merge:
            continue

        # Perform table merge
        merged_html = perform_table_merge(
            soup1, soup2, previous_table_block, wait_merge_table_footnotes
        )

        # Update HTML of previous_table_block
        for block in previous_table_block["blocks"]:
            if (block["type"] == BlockType.TABLE_BODY and block["lines"] and block["lines"][0]["spans"]):
                block["lines"][0]["spans"][0]["html"] = merged_html
                break

        # Delete current page table
        for block in current_table_block["blocks"]:
            block['lines'] = []
            block[SplitFlag.LINES_DELETED] = True

