# Copyright (c) Opendatalab. All rights reserved.
import sys
import types
from pathlib import Path
from unittest import mock


def install_import_stubs() -> None:
    if "loguru" not in sys.modules:
        loguru = types.ModuleType("loguru")
        loguru.logger = types.SimpleNamespace(
            debug=lambda *a, **k: None,
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            exception=lambda *a, **k: None,
        )
        sys.modules["loguru"] = loguru


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
install_import_stubs()

from vparse.result import OCRResult, PageInfo, BlockInfo

def test_ocr_result_structure():
    """Test that OCRResult correctly wraps the raw middle_json dictionary."""
    mock_json = [
        {
            "page_idx": 0,
            "page_size": [612.0, 792.0],
            "para_blocks": [
                {"type": "text", "bbox": [10.0, 10.0, 100.0, 50.0], "content": "Hello World"}
            ]
        }
    ]
    
    result = OCRResult(mock_json)
    
    assert result.num_pages == 1
    assert result.pages[0].width == 612.0
    assert result.pages[0].blocks[0].type == "text"
    assert result.pages[0].blocks[0].content == "Hello World"

def test_ocr_result_accessors():
    """Test that OCRResult exposes markdown, content list, and raw middle_json."""
    mock_json = [
        {
            "page_idx": 0,
            "page_size": [612.0, 792.0],
            "para_blocks": []
        }
    ]
    engine_output = types.ModuleType("vparse.backend.engine.output")

    def union_make(pdf_info, make_mode, img_buket_path=""):
        del pdf_info, img_buket_path
        if make_mode == "content_list":
            return [{"type": "text", "text": "mock-content", "page_idx": 0}]
        return "mock-markdown"

    engine_output.union_make = union_make

    result = OCRResult({"pdf_info": mock_json, "_backend": "pipeline"})

    with mock.patch.dict(sys.modules, {"vparse.backend.engine.output": engine_output}):
        assert result.markdown() == "mock-markdown"
        assert result.content_list() == [{"type": "text", "text": "mock-content", "page_idx": 0}]
        assert result.middle_json()["pdf_info"] == mock_json

if __name__ == "__main__":
    test_ocr_result_structure()
    test_ocr_result_accessors()
    print("test_result.py passed!")
