# Copyright (c) Opendatalab. All rights reserved.
import sys
import types
import unittest
from unittest import mock

from mineru.cli import common as legacy_common
from mineru.model.ocr.tesseract import TesseractOCRModel as LegacyTesseractOCRModel
from vparse.cli import common
from vparse.model.ocr.tesseract import TesseractOCRModel


class PipelineLiteTests(unittest.TestCase):
    def test_legacy_imports_alias_vparse_modules(self):
        self.assertIs(legacy_common, common)
        self.assertIs(LegacyTesseractOCRModel, TesseractOCRModel)

    def test_get_pipeline_subdir(self):
        self.assertEqual(common.get_pipeline_subdir("pipeline", "auto"), "auto")
        self.assertEqual(
            common.get_pipeline_subdir("pipeline-lite", "ocr"),
            "pipeline_lite_ocr",
        )

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

    def test_do_parse_routes_pipeline_lite_to_pipeline_handler(self):
        captured = {}

        def fake_prepare(pdf_bytes_list, start_page_id, end_page_id):
            captured["prepare"] = (pdf_bytes_list, start_page_id, end_page_id)
            return pdf_bytes_list

        def fake_process_pipeline(
            output_dir,
            pdf_file_names,
            pdf_bytes_list,
            p_lang_list,
            backend,
            parse_method,
            formula_enable,
            table_enable,
            *args,
            **kwargs,
        ):
            captured["backend"] = backend
            captured["parse_method"] = parse_method
            captured["formula_enable"] = formula_enable
            captured["table_enable"] = table_enable
            captured["output_dir"] = output_dir
            captured["pdf_file_names"] = pdf_file_names
            captured["pdf_bytes_list"] = pdf_bytes_list
            captured["p_lang_list"] = p_lang_list

        with mock.patch.object(common, "_prepare_pdf_bytes", side_effect=fake_prepare):
            with mock.patch.object(common, "_process_pipeline", side_effect=fake_process_pipeline):
                common.do_parse(
                    output_dir="./output",
                    pdf_file_names=["sample"],
                    pdf_bytes_list=[b"pdf-bytes"],
                    p_lang_list=["en"],
                    backend="pipeline-lite",
                    parse_method="ocr",
                    formula_enable=False,
                    table_enable=False,
                    start_page_id=1,
                    end_page_id=2,
                )

        self.assertEqual(captured["backend"], "pipeline-lite")
        self.assertEqual(captured["parse_method"], "ocr")
        self.assertFalse(captured["formula_enable"])
        self.assertFalse(captured["table_enable"])
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
