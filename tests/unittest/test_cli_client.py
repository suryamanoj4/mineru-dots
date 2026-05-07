import importlib
import sys
import types
from pathlib import Path
from unittest import mock

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
TEST_PDF_PATH = Path(__file__).with_name("pdfs") / "test.pdf"


def install_import_stubs() -> None:
    loguru = sys.modules.get("loguru") or types.ModuleType("loguru")
    logger = getattr(loguru, "logger", types.SimpleNamespace())
    for name in ("debug", "info", "warning", "error", "exception", "remove", "add"):
        if not hasattr(logger, name):
            setattr(logger, name, lambda *a, **k: None)
    loguru.logger = logger
    sys.modules["loguru"] = loguru

    common = types.ModuleType("vparse.cli.common")
    common.do_parse = lambda *a, **k: None
    common.read_fn = lambda path: Path(path).read_bytes()
    common.pdf_suffixes = ["pdf"]
    common.image_suffixes = ["png", "jpg", "jpeg"]
    sys.modules["vparse.cli.common"] = common

    streaming = types.ModuleType("vparse.cli.streaming")
    streaming.stream_parse = lambda *a, **k: "/tmp/fake-stream-session"
    sys.modules["vparse.cli.streaming"] = streaming

    model_utils = types.ModuleType("vparse.utils.model_utils")
    model_utils.get_vram = lambda device: 1
    sys.modules["vparse.utils.model_utils"] = model_utils

    guess_suffix = types.ModuleType("vparse.utils.guess_suffix_or_lang")
    guess_suffix.guess_suffix_by_path = lambda path: "pdf"
    sys.modules["vparse.utils.guess_suffix_or_lang"] = guess_suffix


install_import_stubs()
cli_client = importlib.import_module("vparse.cli.client")


class FakeVParse:
    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.process_batch_calls = []
        FakeVParse.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

    def process_batch(self, input_paths, **kwargs):
        self.process_batch_calls.append((list(input_paths), kwargs))
        return []


def test_cli_uses_vparse_wrapper_with_limited_outputs():
    runner = CliRunner()

    with runner.isolated_filesystem():
        output_dir = str(Path("out"))
        with mock.patch.object(cli_client, "VParse", FakeVParse):
            result = runner.invoke(
                cli_client.main,
                [
                    "-p",
                    str(TEST_PDF_PATH),
                    "-o",
                    output_dir,
                    "-b",
                    "pipeline",
                    "-l",
                    "en",
                ],
            )

    assert result.exit_code == 0, result.output
    assert len(FakeVParse.instances) == 1

    client = FakeVParse.instances[0]
    assert client.init_kwargs["backend"] == "pipeline"
    assert client.init_kwargs["lang"] == "en"
    assert client.process_batch_calls

    input_paths, call_kwargs = client.process_batch_calls[0]
    assert input_paths == [TEST_PDF_PATH]
    assert call_kwargs["output_dir"] == output_dir
    assert call_kwargs["method"] == "auto"
    assert call_kwargs["draw_layout_bbox"] is True
    assert call_kwargs["draw_span_bbox"] is False
    assert call_kwargs["dump_md"] is True
    assert call_kwargs["dump_content_list"] is True
    assert call_kwargs["dump_middle_json"] is False
    assert call_kwargs["dump_model_output"] is False
    assert call_kwargs["dump_orig_pdf"] is False
