#!/usr/bin/env python3
"""
Script to count total pages from *_content_list.json files in the output directory.

Usage:
    python count_pages.py <output_directory>
    
Example:
    python count_pages.py /path/to/output
"""

import json
import sys
from pathlib import Path


def count_pages_from_content_list(output_dir: str):
    output_path = Path(output_dir)
    
    if not output_path.exists():
        logger.error(f"Output directory does not exist: {output_dir}")
        sys.exit(1)
    
    # Find all *_content_list.json files
    content_list_files = list(output_path.rglob("*_content_list.json"))
    
    if not content_list_files:
        print("Total files found: 0")
        print("Total pages: 0")
        return
    
    total_pages = 0
    valid_files = 0
    
    for json_file in content_list_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                content_list = json.load(f)
            
            if not isinstance(content_list, list):
                continue
            
            # Extract unique page_idx values
            page_indices = set()
            for item in content_list:
                if isinstance(item, dict) and "page_idx" in item:
                    page_indices.add(item["page_idx"])
            
            total_pages += len(page_indices)
            valid_files += 1
            
        except Exception:
            continue
    
    print(f"Total files found: {valid_files}")
    print(f"Total pages: {total_pages}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_pages.py <output_directory>")
        sys.exit(1)
    
    output_directory = sys.argv[1]
    count_pages_from_content_list(output_directory)
