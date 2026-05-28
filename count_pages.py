#!/usr/bin/env python3
"""
Count total pages from output directory.

Auto-detects available output files:
  - *_layout.pdf (fast, via pypdfium2) — falls back to
  - *_content_list.json (slow)

Usage:
    python count_pages.py <output_directory>
"""

import json
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def count_from_pdf(output_dir: str) -> tuple[int, int, str] | None:
    import pypdfium2 as pdfium
    from tqdm import tqdm

    pdf_files = sorted(Path(output_dir).rglob("*_layout.pdf"))
    source_label = "layout PDFs"
    if not pdf_files:
        pdf_files = sorted(Path(output_dir).rglob("*_origin.pdf"))
        source_label = "origin PDFs"
    if not pdf_files:
        return None

    def count_pages(path: Path) -> int:
        try:
            doc = pdfium.PdfDocument(str(path))
            n = len(doc)
            doc.close()
            return n
        except Exception:
            return 0

    total = 0
    n = len(pdf_files)
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut_map = {pool.submit(count_pages, f): f for f in pdf_files}
        for fut in tqdm(as_completed(fut_map), total=n, desc="Counting pages", unit="pdf"):
            total += fut.result()

    return n, total, source_label


def count_from_json(output_dir: str) -> tuple[int, int]:
    from tqdm import tqdm

    output_path = Path(output_dir)
    if not output_path.exists():
        return 0, 0

    content_files = list(output_path.rglob("*_content_list.json"))
    if not content_files:
        return 0, 0

    total_pages = 0
    valid_files = 0
    for f in tqdm(content_files, desc="Counting pages", unit="json"):
        try:
            with open(f, encoding="utf-8") as fh:
                cl = json.load(fh)
            if not isinstance(cl, list):
                continue
            pages = {item["page_idx"] for item in cl if isinstance(item, dict) and "page_idx" in item}
            total_pages += len(pages)
            valid_files += 1
        except Exception:
            continue

    return valid_files, total_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count total pages in output directory")
    parser.add_argument("directory", help="Output directory")
    args = parser.parse_args()

    result = count_from_pdf(args.directory)
    if result is not None:
        files, pages, label = result
        print(f"Counted from {label}")
    else:
        files, pages = count_from_json(args.directory)
        print(f"Counted from content_list JSONs")

    print(f"Total files: {files}")
    print(f"Total pages: {pages}")
