#!/usr/bin/env python3
"""
Count total pages from output directory.

Auto-detects:
  - *_origin.pdf (fast, via pypdfium2) — falls back to
  - *_content_list.json (slower, parallelized)

Usage:
    python count_pages.py <output_directory>
"""

import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def _count_pdf_pages(path: Path) -> int:
    import pypdfium2 as pdfium
    try:
        doc = pdfium.PdfDocument(str(path))
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


def _count_json_pages(path: Path) -> tuple[int, int]:
    try:
        with open(path, encoding="utf-8") as fh:
            cl = json.load(fh)
        if not isinstance(cl, list):
            return 0, 0
        pages = {item["page_idx"] for item in cl if isinstance(item, dict) and "page_idx" in item}
        return 1, len(pages)
    except Exception:
        return 0, 0


def count_from_pdf(output_dir: str) -> tuple[int, int] | None:
    from tqdm import tqdm

    origin_files = sorted(Path(output_dir).rglob("*_origin.pdf"))
    if not origin_files:
        return None

    total = 0
    n = len(origin_files)
    pbar = tqdm(total=n, desc="Counting pages", unit="pdf")
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut_map = {pool.submit(_count_pdf_pages, f): f for f in origin_files}
        for fut in as_completed(fut_map):
            total += fut.result()
            pbar.set_description(f"Pages: {total}")
            pbar.update(1)
    pbar.close()

    return n, total


def count_from_json(output_dir: str) -> tuple[int, int]:
    from tqdm import tqdm

    content_files = sorted(Path(output_dir).rglob("*_content_list.json"))
    if not content_files:
        return 0, 0

    total_pages = 0
    valid_files = 0
    n = len(content_files)
    pbar = tqdm(total=n, desc="Counting pages", unit="json")
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut_map = {pool.submit(_count_json_pages, f): f for f in content_files}
        for fut in as_completed(fut_map):
            f_result = fut.result()
            valid_files += f_result[0]
            total_pages += f_result[1]
            pbar.set_description(f"Pages: {total_pages}")
            pbar.update(1)
    pbar.close()

    return valid_files, total_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count total pages in output directory")
    parser.add_argument("directory", help="Output directory")
    args = parser.parse_args()

    result = count_from_pdf(args.directory)
    if result is not None:
        files, pages = result
        print(f"Counted from origin PDFs")
    else:
        files, pages = count_from_json(args.directory)
        print(f"Counted from content_list JSONs")

    print(f"Total files: {files}")
    print(f"Total pages: {pages}")
