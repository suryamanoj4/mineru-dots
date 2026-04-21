# Copyright (c) Opendatalab. All rights reserved.
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from vparse.utils.enum_class import MakeMode


class BlockInfo(BaseModel):
    """Information about a single layout block (paragraph, image, table, etc.)."""
    type: str = Field(description="Type of the block (text, title, image, table, etc.)")
    bbox: List[float] = Field(description="Bounding box [x0, y0, x1, y1]")
    content: Optional[str] = Field(default=None, description="Text content of the block if applicable")
    page_idx: int = Field(description="Index of the page this block belongs to")
    # Blocks can be nested (e.g., Table contains TableBody, TableCaption)
    blocks: Optional[List["BlockInfo"]] = Field(default=None, description="Nested blocks")


class PageInfo(BaseModel):
    """Information about a single document page."""
    page_idx: int = Field(description="Zero-based index of the page")
    width: float = Field(description="Width of the page in points")
    height: float = Field(description="Height of the page in points")
    blocks: List[BlockInfo] = Field(default_factory=list, description="List of blocks on this page")


class OCRResult:
    """
    Structured result of an OCR processing job.
    
    Wraps the raw 'middle_json' dictionary and provides clean accessors.
    """

    def __init__(self, middle_json: List[Dict[str, Any]], output_dir: Optional[Path] = None):
        """
        Initialize with raw middle_json and optional output directory.
        
        Note: middle_json in VParse is typically a list of dicts, where each dict 
        represents a page's information.
        """
        self._raw = middle_json
        self._output_dir = output_dir

    @property
    def pages(self) -> List[PageInfo]:
        """Get a list of structured PageInfo objects."""
        pages = []
        for i, raw_page in enumerate(self._raw):
            blocks = []
            # Extract blocks from 'para_blocks' (standard) or other possible keys
            raw_blocks = raw_page.get("para_blocks", [])
            for raw_block in raw_blocks:
                blocks.append(self._parse_block(raw_block, i))
            
            w, h = raw_page.get("page_size", [0.0, 0.0])
            pages.append(PageInfo(
                page_idx=raw_page.get("page_idx", i),
                width=float(w),
                height=float(h),
                blocks=blocks
            ))
        return pages

    def _parse_block(self, raw_block: Dict[str, Any], page_idx: int) -> BlockInfo:
        """Recursively parse raw block dictionaries into BlockInfo objects."""
        nested = None
        if "blocks" in raw_block:
            nested = [self._parse_block(b, page_idx) for b in raw_block["blocks"]]
            
        return BlockInfo(
            type=raw_block.get("type", "unknown"),
            bbox=raw_block.get("bbox", [0.0, 0.0, 0.0, 0.0]),
            content=raw_block.get("content"), # This might need to be merged text in some backends
            page_idx=page_idx,
            blocks=nested
        )

    @property
    def num_pages(self) -> int:
        """Get the total number of pages."""
        return len(self._raw)

    @property
    def output_dir(self) -> Optional[Path]:
        """Get the path to the directory containing output files (images, etc.)."""
        return self._output_dir

    def markdown(self, mode: str = MakeMode.MM_MD) -> str:
        """
        Get the final Markdown representation.
        
        Args:
            mode: Either 'mm_markdown' (multimodal) or 'nlp_markdown'.
        """
        # In a real scenario, we might import union_make here to avoid circular imports
        from vparse.backend.pipeline.pipeline_middle_json_mkcontent import union_make
        return union_make(self._raw, mode)

    def content_list(self) -> List[Dict[str, Any]]:
        """Get the simplified content list format (useful for RAG)."""
        from vparse.backend.pipeline.pipeline_middle_json_mkcontent import union_make
        return union_make(self._raw, MakeMode.CONTENT_LIST)

    def middle_json(self) -> List[Dict[str, Any]]:
        """Get the raw middle_json representation."""
        return self._raw

    def __repr__(self) -> str:
        return f"<OCRResult pages={self.num_pages} output_dir='{self.output_dir}'>"
