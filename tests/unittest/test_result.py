# Copyright (c) Opendatalab. All rights reserved.
from vparse import OCRResult, PageInfo, BlockInfo

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
    """Test that OCRResult provides access to different output formats."""
    mock_json = [
        {
            "page_idx": 0,
            "page_size": [612.0, 792.0],
            "para_blocks": []
        }
    ]
    result = OCRResult(mock_json)
    
    # middle_json should return the original data
    assert result.middle_json() == mock_json
    # num_pages should match the list length
    assert result.num_pages == 1

if __name__ == "__main__":
    test_ocr_result_structure()
    test_ocr_result_accessors()
    print("test_result.py passed!")
