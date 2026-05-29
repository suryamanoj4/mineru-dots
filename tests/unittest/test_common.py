# Copyright (c) Opendatalab. All rights reserved.
import sys
import types
import unittest
from unittest import mock


def install_import_stubs() -> None:
    loguru = sys.modules.get("loguru") or types.ModuleType("loguru")
    logger = getattr(loguru, "logger", types.SimpleNamespace())
    for name in ("debug", "info", "warning", "error", "exception"):
        if not hasattr(logger, name):
            setattr(logger, name, lambda *a, **k: None)
    loguru.logger = logger
    sys.modules["loguru"] = loguru

    draw_bbox = types.ModuleType("vparse.utils.draw_bbox")
    draw_bbox.draw_layout_bbox = lambda *a, **k: None
    draw_bbox.draw_span_bbox = lambda *a, **k: None
    draw_bbox.draw_line_sort_bbox = lambda *a, **k: None
    sys.modules["vparse.utils.draw_bbox"] = draw_bbox

    engine_utils = types.ModuleType("vparse.utils.engine_utils")
    engine_utils.get_vlm_engine = lambda *a, **k: "http-client"
    sys.modules["vparse.utils.engine_utils"] = engine_utils

    guess_suffix = types.ModuleType("vparse.utils.guess_suffix_or_lang")
    guess_suffix.guess_suffix_by_bytes = lambda file_bytes, file_path=None: "pdf"
    guess_suffix.guess_suffix_by_path = lambda path: "pdf"
    sys.modules["vparse.utils.guess_suffix_or_lang"] = guess_suffix

    vlm_middle = types.ModuleType("vparse.backend.vlm.vlm_middle_json_mkcontent")
    vlm_middle.union_make = lambda *a, **k: ""
    sys.modules["vparse.backend.vlm.vlm_middle_json_mkcontent"] = vlm_middle

    vlm_analyze = types.ModuleType("vparse.backend.vlm.vlm_analyze")
    vlm_analyze.doc_analyze = lambda *a, **k: ({}, None)

    async def aio_doc_analyze(*args, **kwargs):
        return ({}, None)

    vlm_analyze.aio_doc_analyze = aio_doc_analyze
    sys.modules["vparse.backend.vlm.vlm_analyze"] = vlm_analyze

    pytorch_paddle = types.ModuleType("vparse.model.ocr.pytorch_paddle")

    class PytorchPaddleOCR:
        pass

    pytorch_paddle.PytorchPaddleOCR = PytorchPaddleOCR
    sys.modules["vparse.model.ocr.pytorch_paddle"] = pytorch_paddle
    sys.modules["mineru.model.ocr.pytorch_paddle"] = pytorch_paddle

    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        pdfium = types.ModuleType("pypdfium2")
        pdfium.PdfPage = object
        pdfium.PdfDocument = object
        sys.modules["pypdfium2"] = pdfium

    try:
        import numpy  # noqa: F401
    except ImportError:
        numpy = types.ModuleType("numpy")
        numpy.ndarray = object
        sys.modules["numpy"] = numpy

    try:
        from PIL import Image, ImageOps  # noqa: F401
    except ImportError:
        pil = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        image_ops_module = types.ModuleType("PIL.ImageOps")
        image_module.Image = object
        pil.Image = image_module
        pil.ImageOps = image_ops_module
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image_module
        sys.modules["PIL.ImageOps"] = image_ops_module


install_import_stubs()

from mineru.cli import common as legacy_common
from mineru.model.ocr.tesseract import TesseractOCRModel as LegacyTesseractOCRModel
from vparse.cli import common
from vparse.model.ocr.tesseract import TesseractOCRModel


class VparseCommonTests(unittest.TestCase):
    def test_legacy_imports_alias_vparse_modules(self):
        self.assertIs(legacy_common, common)
        self.assertIs(LegacyTesseractOCRModel, TesseractOCRModel)

    def test_get_pipeline_subdir(self):
        self.assertEqual(common.get_pipeline_subdir("pipeline", "auto"), "auto")

    def test_temporary_env_restores_previous_value(self):
        with mock.patch.dict(common.os.environ, {"MINERU_OCR_ENGINE": "paddle"}, clear=False):
            with common.temporary_env(MINERU_OCR_ENGINE="tesseract"):
                self.assertEqual(common.os.environ["MINERU_OCR_ENGINE"], "tesseract")

            self.assertEqual(common.os.environ["MINERU_OCR_ENGINE"], "paddle")

    def test_vparse_env_preferred_with_mineru_fallback(self):
        with mock.patch.dict(common.os.environ, {}, clear=False):
            common.os.environ.pop("VPARSE_OCR_ENGINE", None)
            common.os.environ.pop("MINERU_OCR_ENGINE", None)

            common.os.environ["MINERU_OCR_ENGINE"] = "tesseract"
            self.assertEqual(
                common.get_env_with_legacy("VPARSE_OCR_ENGINE", "MINERU_OCR_ENGINE", "paddle"),
                "tesseract",
            )

            common.os.environ["VPARSE_OCR_ENGINE"] = "paddle"
            self.assertEqual(
                common.get_env_with_legacy("VPARSE_OCR_ENGINE", "MINERU_OCR_ENGINE", "tesseract"),
                "paddle",
            )

    def test_do_parse_routes_lite_to_lite_handler(self):
        captured = {}

        def fake_prepare(pdf_bytes_list, start_page_id, end_page_id):
            captured["prepare"] = (pdf_bytes_list, start_page_id, end_page_id)
            return pdf_bytes_list

        def fake_process_lite(
            output_dir,
            pdf_file_names,
            pdf_bytes_list,
            p_lang_list,
            backend,
            parse_method,
            *args,
            **kwargs,
        ):
            captured["backend"] = backend
            captured["parse_method"] = parse_method
            captured["output_dir"] = output_dir
            captured["pdf_file_names"] = pdf_file_names
            captured["pdf_bytes_list"] = pdf_bytes_list
            captured["p_lang_list"] = p_lang_list

        with mock.patch.object(common, "_prepare_pdf_bytes", side_effect=fake_prepare):
            with mock.patch.object(common, "_process_lite", side_effect=fake_process_lite):
                common.do_parse(
                    output_dir="./output",
                    pdf_file_names=["sample"],
                    pdf_bytes_list=[b"pdf-bytes"],
                    p_lang_list=["en"],
                    backend="lite",
                    parse_method="ocr",
                    start_page_id=1,
                    end_page_id=2,
                )

        self.assertEqual(captured["backend"], "lite")
        self.assertEqual(captured["parse_method"], "ocr")
        self.assertEqual(captured["pdf_file_names"], ["sample"])
        self.assertEqual(captured["pdf_bytes_list"], [b"pdf-bytes"])
        self.assertEqual(captured["p_lang_list"], ["en"])
        self.assertEqual(captured["prepare"][1:], (1, 2))

    def test_tesseract_lang_alias(self):
        fake_pytesseract = types.ModuleType("pytesseract")
        fake_pytesseract.Output = types.SimpleNamespace(DICT=object())
        fake_pytesseract.pytesseract = types.SimpleNamespace(
            tesseract_cmd="/usr/bin/tesseract"
        )
        fake_pytesseract.image_to_data = lambda *args, **kwargs: {}

        with mock.patch("shutil.which", return_value="/usr/bin/tesseract"):
            with mock.patch.dict(sys.modules, {"pytesseract": fake_pytesseract}):
                model = TesseractOCRModel(lang="en")

        self.assertEqual(model.lang, "eng")


if __name__ == "__main__":
    unittest.main()
