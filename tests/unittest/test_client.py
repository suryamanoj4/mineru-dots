import contextlib
import importlib
import json
import sys
import tempfile
import types
import unittest
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
            remove=lambda *a, **k: None,
            add=lambda *a, **k: None,
        )
        sys.modules["loguru"] = loguru


def build_fake_cli_common(calls: list[dict]) -> types.ModuleType:
    module = types.ModuleType("vparse.cli.common")
    module.pdf_suffixes = ["pdf"]
    module.image_suffixes = ["png", "jpg", "jpeg"]

    @contextlib.contextmanager
    def temporary_env(**updates):
        del updates
        yield

    def get_pipeline_subdir(backend: str, parse_method: str) -> str:
        if backend == "pipeline":
            return parse_method
        if backend == "lite":
            return f"lite_{parse_method}"
        return f"{backend.replace('-', '_')}_{parse_method}"

    def read_fn(path):
        return Path(path).read_bytes()

    def do_parse(
        output_dir,
        pdf_file_names,
        pdf_bytes_list,
        p_lang_list,
        backend="pipeline",
        parse_method="auto",
        formula_enable=True,
        table_enable=True,
        server_url=None,
        f_draw_layout_bbox=True,
        f_draw_span_bbox=True,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=True,
        f_dump_orig_pdf=True,
        f_dump_content_list=True,
        f_make_md_mode="mm_markdown",
        start_page_id=0,
        end_page_id=None,
        **kwargs,
    ):
        calls.append(
            {
                "output_dir": output_dir,
                "pdf_file_names": list(pdf_file_names),
                "pdf_bytes_list": list(pdf_bytes_list),
                "p_lang_list": list(p_lang_list),
                "backend": backend,
                "parse_method": parse_method,
                "formula_enable": formula_enable,
                "table_enable": table_enable,
                "server_url": server_url,
                "f_draw_layout_bbox": f_draw_layout_bbox,
                "f_draw_span_bbox": f_draw_span_bbox,
                "f_dump_md": f_dump_md,
                "f_dump_middle_json": f_dump_middle_json,
                "f_dump_model_output": f_dump_model_output,
                "f_dump_orig_pdf": f_dump_orig_pdf,
                "f_dump_content_list": f_dump_content_list,
                "f_make_md_mode": f_make_md_mode,
                "start_page_id": start_page_id,
                "end_page_id": end_page_id,
                "kwargs": kwargs,
            }
        )

        output_root = Path(output_dir)
        for index, pdf_name in enumerate(pdf_file_names):
            if backend in {"pipeline", "lite"}:
                subdir = get_pipeline_subdir(backend, parse_method)
                backend_label = backend
            elif backend.startswith("vlm-"):
                subdir = "vlm"
                backend_label = "vlm"
            elif backend.startswith("hybrid-"):
                subdir = f"hybrid_{parse_method}"
                backend_label = "hybrid"
            else:
                subdir = parse_method
                backend_label = backend

            parse_dir = output_root / pdf_name / subdir
            images_dir = parse_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [612.0, 792.0],
                        "para_blocks": [
                            {
                                "type": "text",
                                "bbox": [0.0, 0.0, 10.0, 10.0],
                                "content": f"mock:{pdf_name}:{index}",
                            }
                        ],
                    }
                ],
                "_backend": backend_label,
            }
            with open(parse_dir / f"{pdf_name}_middle.json", "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

    module.temporary_env = temporary_env
    module.get_pipeline_subdir = get_pipeline_subdir
    module.read_fn = read_fn
    module.do_parse = do_parse
    return module


def build_real_common_import_stubs() -> dict[str, types.ModuleType]:
    draw_bbox = types.ModuleType("vparse.utils.draw_bbox")
    draw_bbox.draw_layout_bbox = lambda *a, **k: None
    draw_bbox.draw_span_bbox = lambda *a, **k: None
    draw_bbox.draw_line_sort_bbox = lambda *a, **k: None

    engine_utils = types.ModuleType("vparse.utils.engine_utils")
    engine_utils.get_vlm_engine = lambda *a, **k: "http-client"

    guess_suffix = types.ModuleType("vparse.utils.guess_suffix_or_lang")
    guess_suffix.guess_suffix_by_bytes = lambda file_bytes, file_path=None: "pdf"

    pdf_image_tools = types.ModuleType("vparse.utils.pdf_image_tools")
    pdf_image_tools.images_bytes_to_pdf_bytes = lambda file_bytes: file_bytes

    engine_output = types.ModuleType("vparse.backend.engine.output")

    def engine_union_make(pdf_info, make_mode, img_buket_path=""):
        del img_buket_path
        if make_mode == "content_list":
            return [
                {
                    "type": "text",
                    "text": "integration-content",
                    "page_idx": pdf_info[0].get("page_idx", 0),
                }
            ]
        return "integration-markdown"

    engine_output.union_make = engine_union_make

    vlm_middle = types.ModuleType("vparse.backend.vlm.vlm_middle_json_mkcontent")
    vlm_middle.union_make = lambda pdf_info, make_mode, img_buket_path="": []

    vlm_analyze = types.ModuleType("vparse.backend.vlm.vlm_analyze")
    vlm_analyze.doc_analyze = lambda *a, **k: ({}, None)

    async def aio_doc_analyze(*args, **kwargs):
        return ({}, None)

    vlm_analyze.aio_doc_analyze = aio_doc_analyze

    lite_analyze = types.ModuleType("vparse.backend.lite.lite_analyze")

    def lite_doc_analyze(pdf_bytes, image_writer=None, lang="eng", **kwargs):
        del pdf_bytes, image_writer, lang, kwargs
        return (
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "page_size": [612.0, 792.0],
                        "para_blocks": [
                            {
                                "index": 0,
                                "type": "text",
                                "bbox": [10.0, 10.0, 100.0, 50.0],
                                "lines": [],
                            }
                        ],
                        "discarded_blocks": [],
                    }
                ],
                "_backend": "lite",
            },
            None,
        )

    lite_analyze.doc_analyze = lite_doc_analyze

    pipeline_middle = types.ModuleType("vparse.backend.pipeline.pipeline_middle_json_mkcontent")

    def union_make(pdf_info, make_mode, img_buket_path=""):
        del img_buket_path
        if make_mode == "content_list":
            return [
                {
                    "type": "text",
                    "text": "integration-content",
                    "page_idx": pdf_info[0].get("page_idx", 0),
                }
            ]
        return "integration-markdown"

    pipeline_middle.union_make = union_make

    pypdfium2 = types.ModuleType("pypdfium2")
    pypdfium2.PdfDocument = object

    requests = types.ModuleType("requests")
    requests.get = lambda *a, **k: types.SimpleNamespace(content=b"")
    requests.post = lambda *a, **k: types.SimpleNamespace(status_code=200)

    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *a, **k: object()

    botocore = types.ModuleType("botocore")
    botocore_config = types.ModuleType("botocore.config")

    class FakeBotocoreConfig:
        def __init__(self, *args, **kwargs):
            pass

    botocore_config.Config = FakeBotocoreConfig

    return {
        "vparse.utils.draw_bbox": draw_bbox,
        "vparse.utils.engine_utils": engine_utils,
        "vparse.utils.guess_suffix_or_lang": guess_suffix,
        "vparse.utils.pdf_image_tools": pdf_image_tools,
        "vparse.backend.engine.output": engine_output,
        "vparse.backend.vlm.vlm_middle_json_mkcontent": vlm_middle,
        "vparse.backend.vlm.vlm_analyze": vlm_analyze,
        "vparse.backend.lite.lite_analyze": lite_analyze,
        "vparse.backend.pipeline.pipeline_middle_json_mkcontent": pipeline_middle,
        "pypdfium2": pypdfium2,
        "requests": requests,
        "boto3": boto3,
        "botocore": botocore,
        "botocore.config": botocore_config,
    }


install_import_stubs()

from vparse import VParse


TEST_PDF_PATH = Path(__file__).with_name("pdfs") / "test.pdf"


class VParseClientTests(unittest.TestCase):
    def test_process_uses_existing_path_and_removes_middle_json_when_not_requested(self):
        calls: list[dict] = []
        fake_common = build_fake_cli_common(calls)

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(sys.modules, {"vparse.cli.common": fake_common}):
                client = VParse(backend="pipeline", lang="en")
                result = client.process(
                    TEST_PDF_PATH,
                    output_dir=temp_dir,
                    method="auto",
                    dump_middle_json=False,
                )

            self.assertEqual(result.num_pages, 1)
            self.assertEqual(result.pages[0].blocks[0].content, "mock:test:0")
            self.assertEqual(calls[0]["pdf_file_names"], ["test"])
            self.assertEqual(calls[0]["backend"], "pipeline")
            self.assertEqual(calls[0]["parse_method"], "auto")
            self.assertEqual(calls[0]["f_make_md_mode"], "mm_markdown")
            self.assertFalse((Path(temp_dir) / "test" / "auto" / "test_middle.json").exists())

    def test_process_accepts_raw_pdf_bytes(self):
        calls: list[dict] = []
        fake_common = build_fake_cli_common(calls)
        raw_pdf = TEST_PDF_PATH.read_bytes()

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(sys.modules, {"vparse.cli.common": fake_common}):
                with mock.patch("vparse.client._guess_input_suffix", return_value="pdf"):
                    client = VParse()
                    result = client.process(raw_pdf, output_dir=temp_dir)

        self.assertEqual(result.pages[0].blocks[0].content, "mock:document:0")
        self.assertEqual(calls[0]["pdf_file_names"], ["document"])
        self.assertEqual(calls[0]["pdf_bytes_list"], [raw_pdf])

    def test_process_batch_reports_progress_and_deduplicates_names(self):
        calls: list[dict] = []
        fake_common = build_fake_cli_common(calls)
        progress_updates: list[tuple[int, int]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(sys.modules, {"vparse.cli.common": fake_common}):
                client = VParse()
                results = client.process_batch(
                    [TEST_PDF_PATH, TEST_PDF_PATH],
                    output_dir=temp_dir,
                    callback=lambda progress, total: progress_updates.append((progress, total)),
                )

        self.assertEqual(len(results), 2)
        self.assertEqual(progress_updates, [(1, 2), (2, 2)])
        self.assertEqual(calls[0]["pdf_file_names"], ["test"])
        self.assertEqual(calls[1]["pdf_file_names"], ["test_2"])
        self.assertEqual(results[0].output_dir.parent.name, "test")
        self.assertEqual(results[1].output_dir.parent.name, "test_2")

    def test_content_list_output_format_stays_compatible_with_do_parse(self):
        calls: list[dict] = []
        fake_common = build_fake_cli_common(calls)

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(sys.modules, {"vparse.cli.common": fake_common}):
                client = VParse(output_format="content_list")
                client.process(TEST_PDF_PATH, output_dir=temp_dir)

        self.assertEqual(client.output_format, "content_list")
        self.assertEqual(calls[0]["f_make_md_mode"], "mm_markdown")
        self.assertIn("pipeline", client.get_available_backends())
        self.assertIn("hybrid-auto-engine", client.get_available_backends())

    def test_context_manager_cleans_up_temporary_output_root(self):
        calls: list[dict] = []
        fake_common = build_fake_cli_common(calls)

        with mock.patch.dict(sys.modules, {"vparse.cli.common": fake_common}):
            with mock.patch("vparse.client._cleanup_device_memory") as cleanup_memory:
                with VParse(device="cpu") as client:
                    result = client.process(TEST_PDF_PATH, output_dir=None)
                    temp_root = result.output_dir.parents[1]
                    self.assertTrue(temp_root.exists())

                self.assertFalse(temp_root.exists())
                cleanup_memory.assert_called_once_with("cpu")

    def test_process_integration_uses_real_do_parse_and_returns_ocr_result_structure(self):
        stubbed_modules = build_real_common_import_stubs()

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(sys.modules, stubbed_modules, clear=False):
                sys.modules.pop("vparse.cli.common", None)
                common = importlib.import_module("vparse.cli.common")

                with mock.patch.object(
                    common,
                    "_prepare_pdf_bytes",
                    side_effect=lambda pdf_bytes_list, start_page_id, end_page_id: pdf_bytes_list,
                ):
                    client = VParse(backend="lite", lang="en")
                    result = client.process(
                        TEST_PDF_PATH,
                        output_dir=temp_dir,
                        dump_md=True,
                        dump_content_list=True,
                        dump_middle_json=True,
                    )
                    self.assertEqual(result.num_pages, 1)
                    self.assertEqual(result.output_dir.name, "lite_auto")
                    self.assertEqual(result.pages[0].page_idx, 0)
                    self.assertEqual(result.pages[0].blocks[0].type, "text")
                    self.assertIsNone(result.pages[0].blocks[0].content)
                    self.assertEqual(result.markdown(), "integration-markdown")
                    self.assertEqual(
                        result.content_list(),
                        [{"type": "text", "text": "integration-content", "page_idx": 0}],
                    )
                    self.assertEqual(result.middle_json()["_backend"], "lite")
                    self.assertTrue((result.output_dir / "test_middle.json").exists())


if __name__ == "__main__":
    unittest.main()
