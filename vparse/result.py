# Copyright (c) Opendatalab. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from pydantic import BaseModel, Field

from vparse.exceptions import InputError
from vparse.utils.enum_class import MakeMode


class BlockInfo(BaseModel):
    """Information about a single layout block (paragraph, image, table, etc.)."""
    block_type: str = Field(description="Type of the block (text, title, image, table, etc.)")
    bbox: tuple[float, float, float, float] = Field(
        description="Bounding box (x0, y0, x1, y1)"
    )
    content: Optional[str] = Field(default=None, description="Text content of the block if applicable")
    page_number: int = Field(description="Zero-based page number this block belongs to")
    # Blocks can be nested (e.g., Table contains TableBody, TableCaption)
    blocks: Optional[List["BlockInfo"]] = Field(default=None, description="Nested blocks")

    @property
    def type(self) -> str:
        return self.block_type

    @property
    def page_idx(self) -> int:
        return self.page_number


class PageInfo(BaseModel):
    """Information about a single document page."""
    page_number: int = Field(description="Zero-based page number")
    width: float = Field(description="Width of the page in points")
    height: float = Field(description="Height of the page in points")
    blocks: List[BlockInfo] = Field(default_factory=list, description="List of blocks on this page")

    @property
    def page_idx(self) -> int:
        return self.page_number


class OCRResult:
    """
    Structured result of an OCR processing job.
    
    Wraps the raw 'middle_json' dictionary and provides clean accessors.
    """

    def __init__(
        self,
        middle_json: Dict[str, Any] | List[Dict[str, Any]],
        output_dir: Optional[Path] = None,
        default_markdown_mode: str = MakeMode.MM_MD,
    ):
        """
        Initialize with raw middle_json, original pdf_bytes and optional output directory.
        
        ``middle_json`` may be either the original backend dictionary or the
        extracted ``pdf_info`` page list for backward compatibility.
        """
        self._raw = middle_json
        self._pdf_bytes = None
        self._output_dir = output_dir
        self._default_markdown_mode = default_markdown_mode
        self._pages = self._build_pages()

    def _raw_pdf_info(self) -> List[Dict[str, Any]]:
        if isinstance(self._raw, dict):
            pdf_info = self._raw.get("pdf_info", [])
            return pdf_info if isinstance(pdf_info, list) else []
        return self._raw

    @property
    def pdf_info(self) -> List[PageInfo]:
        """Get a structured list of document pages."""
        return list(self._pages)

    @property
    def pages(self) -> List[PageInfo]:
        """Compatibility alias for the structured page list."""
        return self.pdf_info

    def _build_pages(self) -> List[PageInfo]:
        pages = []
        for i, raw_page in enumerate(self._raw_pdf_info()):
            page_number = int(raw_page.get("page_idx", i))
            blocks = []
            # Extract blocks from 'para_blocks' (standard) or other possible keys
            raw_blocks = raw_page.get("para_blocks", [])
            for raw_block in raw_blocks:
                blocks.append(self._parse_block(raw_block, page_number))

            w, h = raw_page.get("page_size", [0.0, 0.0])
            pages.append(PageInfo(
                page_number=page_number,
                width=float(w),
                height=float(h),
                blocks=blocks
            ))
        return pages

    def _parse_block(self, raw_block: Dict[str, Any], page_number: int) -> BlockInfo:
        """Recursively parse raw block dictionaries into BlockInfo objects."""
        nested = None
        if "blocks" in raw_block:
            nested = [self._parse_block(b, page_number) for b in raw_block["blocks"]]

        return BlockInfo(
            block_type=str(raw_block.get("type", "unknown")),
            bbox=tuple(float(v) for v in raw_block.get("bbox", [0.0, 0.0, 0.0, 0.0])),
            content=raw_block.get("content"),
            page_number=page_number,
            blocks=nested
        )

    @property
    def num_pages(self) -> int:
        """Get the total number of pages."""
        return len(self._pages)

    @property
    def output_dir(self) -> Optional[Path]:
        """Get the path to the directory containing output files (images, etc.)."""
        return self._output_dir

    def _get_backend(self) -> str:
        if isinstance(self._raw, dict):
            backend = self._raw.get("_backend")
            if isinstance(backend, str) and backend:
                return backend
        return "pipeline"

    def _get_image_dir(self) -> str:
        if self._output_dir is None:
            return ""
        return (self._output_dir / "images").name

    def _render(self, make_mode: str) -> str | List[Dict[str, Any]]:
        image_dir = self._get_image_dir()

        try:
            from vparse.backend.engine.output import union_make as engine_union_make
        except Exception:
            engine_union_make = None

        if engine_union_make is not None:
            return engine_union_make(self._raw_pdf_info(), make_mode, image_dir)

        if self._get_backend() in {"pipeline", "lite"}:
            from vparse.backend.pipeline.pipeline_middle_json_mkcontent import union_make
        else:
            from vparse.backend.vlm.vlm_middle_json_mkcontent import union_make
        return union_make(self._raw_pdf_info(), make_mode, image_dir)

    def markdown(self, mode: str | None = None) -> str:
        """
        Get the final Markdown representation.
        
        Args:
            mode: Either 'mm_markdown' (multimodal) or 'nlp_markdown'.
        """
        render_mode = self._default_markdown_mode if mode is None else mode
        return cast(str, self._render(render_mode))

    def content_list(self) -> List[Dict[str, Any]]:
        """Get the simplified content list format (useful for RAG)."""
        return cast(List[Dict[str, Any]], self._render(MakeMode.CONTENT_LIST))

    def content_list_v2(self) -> List[Any]:
        """Get the page-grouped content list v2 representation."""
        return cast(List[Any], self._render(MakeMode.CONTENT_LIST_V2))

    def middle_json(self) -> Dict[str, Any] | List[Dict[str, Any]]:
        """Get the raw middle_json representation."""
        return self._raw

    def get_page(self, page_num: int) -> PageInfo:
        """Return the structured page object for a zero-based page number."""
        for page in self._pages:
            if page.page_number == page_num:
                return page
        raise InputError(f"Page {page_num} is out of range for a {self.num_pages}-page result")

    def __repr__(self) -> str:
        return f"<OCRResult pages={self.num_pages} output_dir='{self.output_dir}'>"
