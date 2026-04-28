# Copyright (c) Opendatalab. All rights reserved.
import re
from io import BytesIO
import numpy as np
import pypdfium2 as pdfium
from loguru import logger
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.layout import LAParams, LTImage, LTFigure
from pdfminer.converter import PDFPageAggregator


def classify(pdf_bytes):
    """
    Determine if the PDF can have text directly extracted or requires OCR.

    Args:
        pdf_bytes: Byte data of the PDF file

    Returns:
        str: 'txt' for direct text extraction, 'ocr' if OCR is required
    """

    # Load PDF from byte data
    sample_pdf_bytes = extract_pages(pdf_bytes)
    pdf = pdfium.PdfDocument(sample_pdf_bytes)
    try:
        # Get number of PDF pages
        page_count = len(pdf)

        # If PDF page count is 0, return OCR directly
        if page_count == 0:
            return 'ocr'

        # Number of pages to check (check at most 10 pages)
        pages_to_check = min(page_count, 10)

        # Set threshold: if avg valid characters per page < 50, assume OCR is needed
        chars_threshold = 50

        # Check average character count and invalid characters
        if (get_avg_cleaned_chars_per_page(pdf, pages_to_check) < chars_threshold) or detect_invalid_chars(sample_pdf_bytes):
            return 'ocr'

        # Check image coverage
        if get_high_image_coverage_ratio(sample_pdf_bytes, pages_to_check) >= 0.8:
            return 'ocr'

        return 'txt'

    except Exception as e:
        logger.error(f"Error determining PDF type: {e}")
        # Default to OCR on error
        return 'ocr'

    finally:
        # Ensure PDF is closed regardless of the execution path
        pdf.close()


def get_avg_cleaned_chars_per_page(pdf_doc, pages_to_check):
    # Total character count
    total_chars = 0
    # Total cleaned character count
    cleaned_total_chars = 0

    # Check the first few pages of text
    for i in range(pages_to_check):
        page = pdf_doc[i]
        text_page = page.get_textpage()
        text = text_page.get_text_bounded()
        total_chars += len(text)

        # Clean extracted text, remove whitespace
        cleaned_text = re.sub(r'\s+', '', text)
        cleaned_total_chars += len(cleaned_text)

    # Calculate average characters per page
    avg_cleaned_chars_per_page = cleaned_total_chars / pages_to_check

    # logger.debug(f"PDF analysis: average {avg_cleaned_chars_per_page:.1f} cleaned characters per page")

    return avg_cleaned_chars_per_page


def get_high_image_coverage_ratio(sample_pdf_bytes, pages_to_check):
    # Create memory file object
    pdf_stream = BytesIO(sample_pdf_bytes)

    # Create PDF parser
    parser = PDFParser(pdf_stream)

    # Create PDF document object
    document = PDFDocument(parser)

    # Check if document allows text extraction
    if not document.is_extractable:
        # logger.warning("PDF does not allow content extraction")
        return 1.0  # Default to high coverage as content cannot be extracted

    # Create resource manager and parameter objects
    rsrcmgr = PDFResourceManager()
    laparams = LAParams(
        line_overlap=0.5,
        char_margin=2.0,
        line_margin=0.5,
        word_margin=0.1,
        boxes_flow=None,
        detect_vertical=False,
        all_texts=False,
    )

    # Create aggregator
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)

    # Create interpreter
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    # Record number of pages with high image coverage
    high_image_coverage_pages = 0
    page_count = 0

    # Iterate through pages
    for page in PDFPage.create_pages(document):
        # Control number of pages to check
        if page_count >= pages_to_check:
            break

        # Process page
        interpreter.process_page(page)
        layout = device.get_result()

        # Page dimensions
        page_width = layout.width
        page_height = layout.height
        page_area = page_width * page_height

        # Calculate total image coverage area
        image_area = 0

        # Iterate through page elements
        for element in layout:
            # Check if it's an image or graphic element
            if isinstance(element, (LTImage, LTFigure)):
                # Calculate image bounding box area
                img_width = element.width
                img_height = element.height
                img_area = img_width * img_height
                image_area += img_area

        # Calculate coverage ratio
        coverage_ratio = min(image_area / page_area, 1.0) if page_area > 0 else 0
        # logger.debug(f"PDF analysis: page {page_count + 1} image coverage ratio: {coverage_ratio:.2f}")

        # Determine if it's high coverage
        if coverage_ratio >= 0.8:  # Use 80% as threshold for high coverage
            high_image_coverage_pages += 1

        page_count += 1

    # Close resources
    pdf_stream.close()

    # If no pages were processed, return 0
    if page_count == 0:
        return 0.0

    # Calculate proportion of pages with high image coverage
    high_coverage_ratio = high_image_coverage_pages / page_count
    # logger.debug(f"PDF analysis: Proportion of high image coverage pages: {high_coverage_ratio:.2f}")

    return high_coverage_ratio


def extract_pages(src_pdf_bytes: bytes) -> bytes:
    """
    Randomly extract up to 10 pages from PDF byte data and return new PDF bytes.

    Args:
        src_pdf_bytes: Byte data of the PDF file

    Returns:
        bytes: New PDF bytes with extracted pages
    """

    # Load PDF from byte data
    pdf = pdfium.PdfDocument(src_pdf_bytes)

    # Get number of PDF pages
    total_page = len(pdf)
    if total_page == 0:
        # If PDF has no pages, return empty document
        logger.warning("PDF is empty, return empty document")
        return b''

    # Select up to 10 pages
    select_page_cnt = min(10, total_page)

    # Randomly select page indices from total pages
    page_indices = np.random.choice(total_page, select_page_cnt, replace=False).tolist()

    # Create a new PDF document
    sample_docs = pdfium.PdfDocument.new()

    try:
        # Import selected pages to new document
        sample_docs.import_pages(pdf, page_indices)
        pdf.close()

        # Save new PDF to memory buffer
        output_buffer = BytesIO()
        sample_docs.save(output_buffer)

        # Get byte data
        return output_buffer.getvalue()
    except Exception as e:
        pdf.close()
        logger.exception(e)
        return b''  # Return empty bytes on error


def detect_invalid_chars(sample_pdf_bytes: bytes) -> bool:
    """
    Detect if PDF contains invalid characters.
    """
    # pdfminer is slow, so we randomly extract about 10 pages first
    # sample_pdf_bytes = extract_pages(src_pdf_bytes)
    sample_pdf_file_like_object = BytesIO(sample_pdf_bytes)
    laparams = LAParams(
        line_overlap=0.5,
        char_margin=2.0,
        line_margin=0.5,
        word_margin=0.1,
        boxes_flow=None,
        detect_vertical=False,
        all_texts=False,
    )
    text = extract_text(pdf_file=sample_pdf_file_like_object, laparams=laparams)
    text = text.replace("\n", "")
    # logger.info(text)
    # CID character patterns extracted by pdfminer are formatted as (cid:xxx)
    cid_pattern = re.compile(r'\(cid:\d+\)')
    matches = cid_pattern.findall(text)
    cid_count = len(matches)
    cid_len = sum(len(match) for match in matches)
    text_len = len(text)
    if text_len == 0:
        cid_chars_radio = 0
    else:
        cid_chars_radio = cid_count/(cid_count + text_len - cid_len)
    # logger.debug(f"cid_count: {cid_count}, text_len: {text_len}, cid_chars_radio: {cid_chars_radio}")
    # If more than 5% of text is garbled, it's considered an invalid document
    if cid_chars_radio > 0.05:
        return True  # Garbled document
    else:
        return False   # Normal document


if __name__ == '__main__':
    with open('/Users/myhloli/pdf/luanma2x10.pdf', 'rb') as f:
        p_bytes = f.read()
        logger.info(f"PDF Classification Result: {classify(p_bytes)}")