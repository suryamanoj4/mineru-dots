import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def install_optional_dependency_stubs() -> None:
    if "requests" not in sys.modules:
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: types.SimpleNamespace(content=b"")
        requests.post = lambda *args, **kwargs: types.SimpleNamespace(status_code=200)
        sys.modules["requests"] = requests

    if "boto3" not in sys.modules:
        boto3 = types.ModuleType("boto3")
        boto3.client = lambda *args, **kwargs: object()
        sys.modules["boto3"] = boto3

    if "botocore.config" not in sys.modules:
        botocore = types.ModuleType("botocore")
        config_module = types.ModuleType("botocore.config")

        class Config:
            def __init__(self, *args, **kwargs):
                pass

        config_module.Config = Config
        botocore.config = config_module
        sys.modules["botocore"] = botocore
        sys.modules["botocore.config"] = config_module

    if "loguru" not in sys.modules:
        loguru = types.ModuleType("loguru")
        loguru.logger = types.SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None)
        sys.modules["loguru"] = loguru

    if "numpy" not in sys.modules:
        numpy = types.ModuleType("numpy")
        numpy.ndarray = object
        numpy.asarray = lambda value: value
        sys.modules["numpy"] = numpy

    if "pypdfium2" not in sys.modules:
        pdfium = types.ModuleType("pypdfium2")

        class PdfBitmap:
            def to_pil(self):
                return object()

            def close(self):
                pass

        class PdfPage:
            def get_size(self):
                return (100, 100)

            def render(self, scale=1):
                return PdfBitmap()

        class PdfDocument:
            def __init__(self, *args, **kwargs):
                self._pages = [PdfPage()]

            def __len__(self):
                return len(self._pages)

            def __getitem__(self, index):
                return self._pages[index]

            def close(self):
                pass

        pdfium.PdfBitmap = PdfBitmap
        pdfium.PdfPage = PdfPage
        pdfium.PdfDocument = PdfDocument
        sys.modules["pypdfium2"] = pdfium

    if "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        image_ops_module = types.ModuleType("PIL.ImageOps")

        class FakeImage:
            def crop(self, bbox):
                return self

            def save(self, *args, **kwargs):
                pass

            def convert(self, *args, **kwargs):
                return self

        image_module.Image = FakeImage
        image_module.fromarray = lambda value: FakeImage()
        image_module.open = lambda *args, **kwargs: FakeImage()
        pil.Image = image_module
        pil.ImageOps = image_ops_module
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image_module
        sys.modules["PIL.ImageOps"] = image_ops_module


install_optional_dependency_stubs()

from vparse.data.data_reader_writer.multi_bucket_s3 import MultiBucketS3DataReader
from vparse.data.utils.exceptions import (
    CUDA_NOT_AVAILABLE,
    EmptyData,
    FileNotExisted,
    InvalidConfig,
    InvalidParams,
)
from vparse.data.utils.schemas import S3Config
from vparse.exceptions import (
    BackendError,
    ConfigurationError,
    InputError,
    MinerUError,
    ModelLoadError,
    ProcessingError,
    TimeoutError,
    VParseError,
)


TEST_PDF_PATH = Path(__file__).with_name("pdfs") / "test.pdf"


def make_s3_config(bucket_name: str = "mock-bucket") -> S3Config:
    return S3Config(
        bucket_name=bucket_name,
        access_key="mock-access-key",
        secret_key="mock-secret-key",
        endpoint_url="https://mock-s3.local",
        addressing_style="path",
    )


class ExceptionHierarchyTests(unittest.TestCase):
    def test_public_exception_hierarchy_uses_vparse_aliases(self):
        current_module = importlib.import_module("vparse.exceptions")
        legacy_module = importlib.import_module("mineru.exceptions")

        self.assertIs(legacy_module, current_module)
        self.assertIs(MinerUError, VParseError)

        exception_cases = [
            (VParseError("mock-vparse-error"), Exception, "mock-vparse-error"),
            (BackendError("mock-backend-error"), VParseError, "mock-backend-error"),
            (ModelLoadError("mock-model-load-error"), BackendError, "mock-model-load-error"),
            (ConfigurationError("mock-config-error"), VParseError, "mock-config-error"),
            (InputError("mock-input-error"), VParseError, "mock-input-error"),
            (ProcessingError("mock-processing-error"), VParseError, "mock-processing-error"),
            (TimeoutError("mock-timeout-error"), VParseError, "mock-timeout-error"),
            (MinerUError("mock-legacy-error"), VParseError, "mock-legacy-error"),
        ]

        for exc, parent_type, message in exception_cases:
            with self.subTest(exception_type=type(exc).__name__):
                self.assertIsInstance(exc, parent_type)
                self.assertEqual(str(exc), message)

    def test_legacy_exception_subclasses_render_messages_with_mock_data(self):
        mock_missing_path = str(TEST_PDF_PATH.with_name("missing.pdf"))
        exception_cases = [
            (FileNotExisted(mock_missing_path), InputError, f"File {mock_missing_path} does not exist."),
            (InvalidConfig("missing default bucket"), ConfigurationError, "Invalid config: missing default bucket"),
            (InvalidParams("unsupported bucket"), InputError, "Invalid params: unsupported bucket"),
            (EmptyData("mock page payload"), ProcessingError, "Empty data: mock page payload"),
            (CUDA_NOT_AVAILABLE("cuda:mock"), BackendError, "CUDA not available: cuda:mock"),
        ]

        for exc, parent_type, message in exception_cases:
            with self.subTest(exception_type=type(exc).__name__):
                self.assertIsInstance(exc, parent_type)
                self.assertEqual(str(exc), message)

    def test_multi_bucket_reader_validation_raises_phase_two_input_exceptions(self):
        valid_config = make_s3_config()

        with self.assertRaises(InvalidConfig) as empty_prefix_error:
            MultiBucketS3DataReader(default_prefix="", s3_configs=[valid_config])
        self.assertEqual(str(empty_prefix_error.exception), "Invalid config: default_prefix must be provided")

        with self.assertRaises(InvalidConfig) as missing_bucket_error:
            MultiBucketS3DataReader(default_prefix="other-bucket/prefix", s3_configs=[valid_config])
        self.assertIn("default_bucket: other-bucket config must be provided", str(missing_bucket_error.exception))

        with self.assertRaises(InvalidConfig) as duplicate_bucket_error:
            MultiBucketS3DataReader(
                default_prefix="mock-bucket/prefix",
                s3_configs=[make_s3_config("mock-bucket"), make_s3_config("mock-bucket")],
            )
        self.assertIn("must be unique", str(duplicate_bucket_error.exception))

        reader = MultiBucketS3DataReader(
            default_prefix="mock-bucket/prefix",
            s3_configs=[valid_config],
        )
        with self.assertRaises(InvalidParams) as invalid_bucket_error:
            reader.read_at("s3://unknown-bucket/mock.pdf")
        self.assertIn("bucket name: unknown-bucket not found", str(invalid_bucket_error.exception))

    def test_load_images_from_pdf_raises_vparse_timeout_error_for_mock_timeout(self):
        pdf_image_tools = importlib.import_module("vparse.utils.pdf_image_tools")
        pdf_bytes = TEST_PDF_PATH.read_bytes()

        class FakePdfDocument:
            def __init__(self, *_args, **_kwargs):
                self.closed = False

            def __len__(self):
                return 1

            def close(self):
                self.closed = True

        class FakeExecutor:
            def __init__(self):
                self._processes = {}

            def submit(self, *args, **kwargs):
                return object()

            def shutdown(self, wait=False, cancel_futures=True):
                self.shutdown_args = (wait, cancel_futures)

        fake_executor = FakeExecutor()

        with mock.patch.object(pdf_image_tools, "is_windows_environment", return_value=False):
            with mock.patch.object(pdf_image_tools.pdfium, "PdfDocument", FakePdfDocument):
                with mock.patch.object(pdf_image_tools, "ProcessPoolExecutor", return_value=fake_executor):
                    with mock.patch.object(pdf_image_tools, "wait", return_value=(set(), {object()})):
                        with mock.patch.object(pdf_image_tools, "_terminate_executor_processes") as terminate:
                            with self.assertRaises(TimeoutError) as timeout_error:
                                pdf_image_tools.load_images_from_pdf(pdf_bytes, timeout=1, threads=1)

        self.assertEqual(str(timeout_error.exception), "PDF to images conversion timeout after 1s")
        self.assertEqual(terminate.call_count, 2)


if __name__ == "__main__":
    unittest.main()
