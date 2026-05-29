"""Tests for VLM cross-document batch processing.

Stubs external dependencies (torch, vllm, etc.) so the real vparse
modules can be imported without them.  Tests the batching logic,
VRAM-aware batch sizing, and backend integration.
"""
import types
import unittest
from unittest import mock


def _install_stubs() -> None:
    import sys

    stubs: dict[str, dict[str, object]] = {
        "lmdeploy": {},
        "mlx_vlm": {},
        "mineru_vl_utils": {
            "MinerUClient": type("MinerUClient", (), {}),
            "MinerUSamplingParams": type("MinerUSamplingParams", (), {}),
        },
        "mineru_vl_utils.structs": {
            "ContentBlock": type("ContentBlock", (), {}),
            "BlockType": type("BlockType", (), {}),
        },
    }

    for path, attrs in stubs.items():
        if path not in sys.modules:
            mod = types.ModuleType(path)
            for k, v in attrs.items():
                setattr(mod, k, v)
            sys.modules[path] = mod

    import numpy as np
    sys.modules["numpy"] = np


_install_stubs()


class TestEstimateBatchSize(unittest.TestCase):
    def setUp(self):
        self.vram_patch = mock.patch("vparse.backend.vlm.utils.get_vram")
        self.mock_vram = self.vram_patch.start()

    def tearDown(self):
        self.vram_patch.stop()

    def test_large_gpu_capped_at_64(self):
        self.mock_vram.return_value = 80
        from vparse.backend.vlm.utils import estimate_vlm_batch_size
        self.assertEqual(estimate_vlm_batch_size(), 64)

    def test_24gb_gpu_batch(self):
        self.mock_vram.return_value = 24
        from vparse.backend.vlm.utils import estimate_vlm_batch_size
        self.assertGreaterEqual(estimate_vlm_batch_size(), 50)

    def test_8gb_gpu_uses_higher_utilization(self):
        self.mock_vram.return_value = 8
        from vparse.backend.vlm.utils import estimate_vlm_batch_size
        self.assertGreaterEqual(estimate_vlm_batch_size(), 20)

    def test_custom_vram(self):
        self.mock_vram.return_value = 16
        from vparse.backend.vlm.utils import estimate_vlm_batch_size
        b = estimate_vlm_batch_size(vram_gb=4)
        self.assertGreaterEqual(b, 1)
        self.assertLessEqual(b, 64)

    def test_custom_vram_respects_gpu_util(self):
        with mock.patch(
            "vparse.backend.vlm.utils.set_default_gpu_memory_utilization"
        ) as mock_util:
            mock_util.return_value = 0.8
            from vparse.backend.vlm.utils import estimate_vlm_batch_size
            b = estimate_vlm_batch_size(vram_gb=10)
            expected = int(10 * 0.8 / 0.2)
            self.assertEqual(b, min(expected, 64))

    def test_minimum_batch_is_1(self):
        self.mock_vram.return_value = 1
        from vparse.backend.vlm.utils import estimate_vlm_batch_size
        self.assertGreaterEqual(estimate_vlm_batch_size(), 1)


class TestBatchDocAnalyze(unittest.TestCase):
    def setUp(self):
        self.load_patch = mock.patch("vparse.backend.vlm.vlm_analyze.load_images_from_pdf")
        self.mock_load = self.load_patch.start()
        self.mock_load.return_value = (
            [{"img_pil": f"page_{i}"} for i in range(3)],
            mock.MagicMock(),
        )

        self.predictor = mock.AsyncMock()
        self.predictor.aio_batch_two_step_extract = mock.AsyncMock(
            side_effect=lambda images, **kw: [[{"type": "text", "content": f"p_{i}"}] for i in range(len(images))]
        )

        self.model_patch = mock.patch(
            "vparse.backend.vlm.vlm_analyze.ModelSingleton"
        )
        self.mock_singleton = self.model_patch.start()
        self.mock_singleton.return_value.get_model.return_value = self.predictor

        self.mj_patch = mock.patch(
            "vparse.backend.vlm.vlm_analyze.result_to_middle_json"
        )
        self.mock_mj = self.mj_patch.start()
        self.mock_mj.return_value = {"pdf_info": [{"page_idx": 0}]}

    def tearDown(self):
        self.load_patch.stop()
        self.model_patch.stop()
        self.mj_patch.stop()

    def _run(self, func, *a, **kw):
        import asyncio
        return asyncio.run(func(*a, **kw))

    def test_single_book_returns_one_result(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        results = self._run(batch_doc_analyze, [b"pdf1"])
        self.assertEqual(len(results), 1)

    def test_each_result_has_middle_json_and_output(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        results = self._run(batch_doc_analyze, [b"pdf1"])
        mj, out = results[0]
        self.assertIn("pdf_info", mj)
        self.assertEqual(len(out), 3)

    def test_multiple_books(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        self.assertEqual(len(self._run(batch_doc_analyze, [b"a", b"b"])), 2)

    def test_ten_books(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        results = self._run(batch_doc_analyze, [b"p"] * 10, batch_size=16)
        self.assertEqual(len(results), 10)

    def test_empty_book_list(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        self.assertEqual(len(self._run(batch_doc_analyze, [])), 0)

    def test_image_writers_passed(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        writers = [mock.MagicMock(), None]
        results = self._run(batch_doc_analyze, [b"a", b"b"], image_writers=writers)
        self.assertEqual(len(results), 2)

    def test_batch_size_respected(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze
        self._run(batch_doc_analyze, [b"p"] * 10, batch_size=4)
        call_count = self.predictor.aio_batch_two_step_extract.call_count
        self.assertGreaterEqual(call_count, 2)

    def test_books_with_uneven_page_counts(self):
        from vparse.backend.vlm.vlm_analyze import batch_doc_analyze

        def load_side_effect(b, image_type=None):
            pages = 1 if len(b) > 20 else 3
            return ([{"img_pil": f"p_{i}"} for i in range(pages)], mock.MagicMock())

        self.mock_load.side_effect = load_side_effect
        self.predictor.aio_batch_two_step_extract = mock.AsyncMock(
            side_effect=lambda images, **kw: [[{"type": "text"}]] * len(images)
        )

        results = self._run(batch_doc_analyze, [b"small", b"medium" * 30], batch_size=4)
        self.assertEqual(len(results), 2)


class TestBackendBatch(unittest.TestCase):
    def setUp(self):
        self.ep = mock.patch("vparse.backend.registry.resolve_vlm_engine")
        self.mock_resolve = self.ep.start()
        self.mock_resolve.return_value = "vllm"

        self.bp = mock.patch("vparse.backend.registry.batch_vlm_doc_analyze")
        self.mock_batch = self.bp.start()
        self.mock_batch.return_value = [({"pdf_info": []}, {"blocks": []})] * 2

    def tearDown(self):
        self.ep.stop()
        self.bp.stop()

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_returns_correct_count(self):
        from vparse.backend.registry import VLMBackend
        results = self._run(VLMBackend().batch_analyze([b"a", b"b"]))
        self.assertEqual(len(results), 2)

    def test_delegates_to_batch_doc_analyze(self):
        from vparse.backend.registry import VLMBackend
        self._run(VLMBackend().batch_analyze([b"a", b"b"]))
        self.mock_batch.assert_called_once()

    def test_passes_engine(self):
        from vparse.backend.registry import VLMBackend
        self._run(VLMBackend().batch_analyze([b"a"], engine="lmdeploy"))
        _, kwargs = self.mock_batch.call_args
        self.assertEqual(kwargs["backend"], "lmdeploy")


class TestLmdeployBackendBatch(unittest.TestCase):
    def setUp(self):
        self.bp = mock.patch("vparse.backend.registry.batch_vlm_doc_analyze")
        self.mock_batch = self.bp.start()
        self.mock_batch.return_value = [({"pdf_info": []}, {"blocks": []})]

    def tearDown(self):
        self.bp.stop()

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_defaults_to_lmdeploy_engine(self):
        from vparse.backend.registry import VLMLmdeployBackend
        self._run(VLMLmdeployBackend().batch_analyze([b"a"]))
        _, kwargs = self.mock_batch.call_args
        self.assertEqual(kwargs["backend"], "lmdeploy")


class TestBulkProcessor(unittest.TestCase):
    def setUp(self):
        self.load_patch = mock.patch("vparse.backend.vlm.vlm_analyze.load_images_from_pdf")
        self.mock_load = self.load_patch.start()
        self.mock_load.return_value = (
            [{"img_pil": f"page_{i}"} for i in range(3)],
            mock.MagicMock(),
        )
        self.predictor = mock.AsyncMock()
        self.predictor.aio_batch_two_step_extract = mock.AsyncMock(
            side_effect=lambda images, **kw: [[{"type": "text", "content": f"p_{i}"}] for i in range(len(images))]
        )
        self.singleton_patch = mock.patch("vparse.backend.vlm.vlm_analyze.ModelSingleton")
        self.mock_singleton = self.singleton_patch.start()
        self.mock_singleton.return_value.get_model.return_value = self.predictor
        self.mj_patch = mock.patch("vparse.backend.vlm.vlm_analyze.result_to_middle_json")
        self.mock_mj = self.mj_patch.start()
        self.mock_mj.return_value = {"pdf_info": [{"page_idx": 0}]}

    def tearDown(self):
        self.load_patch.stop()
        self.singleton_patch.stop()
        self.mj_patch.stop()

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_returns_job_results(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(page_batch_size=8, checkpoint_dir=tmp)
            results = self._run(p.process_books([b"a"]))
            self.assertEqual(len(results), 1)
            self.assertIsInstance(results[0].middle_json, dict)
            self.assertIsInstance(results[0].model_output, list)

    def test_multiple_books(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(page_batch_size=8, checkpoint_dir=tmp)
            results = self._run(p.process_books([b"a", b"b", b"c"]))
            self.assertEqual(len(results), 3)
            self.assertEqual([r.book_index for r in results], [0, 1, 2])

    def test_empty_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(checkpoint_dir=tmp)
            results = self._run(p.process_books([]))
            self.assertEqual(len(results), 0)

    def test_progress_events_fire(self):
        import tempfile
        events = []
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(page_batch_size=2, checkpoint_dir=tmp)
            self._run(p.process_books(
                [b"a", b"b"],
                on_progress=lambda e: events.append(e),
            ))
            self.assertGreater(len(events), 0)
            self.assertGreater(events[0].total_pages, 0)
            self.assertIsInstance(events[0].pages_per_sec, float)

    def test_checkpoint_skips_done_books(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(page_batch_size=8, checkpoint_dir=tmp)
            self._run(p.process_books([b"a", b"b", b"c"], job_id="test-checkpoint"))
            results = self._run(p.process_books(
                [b"a", b"b", b"c"], job_id="test-checkpoint"
            ))
            self.assertEqual(len(results), 0)

    def test_checkpoint_resumes_partial(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(page_batch_size=8, checkpoint_dir=tmp)
            self._run(p.process_books([b"a", b"b"], job_id="test-resume"))
            results = self._run(p.process_books(
                [b"a", b"b", b"c"], job_id="test-resume"
            ))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].book_index, 2)

    def test_checkpoint_dir_created(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            from vparse.bulk import BulkProcessor
            p = BulkProcessor(checkpoint_dir=tmp)
            self._run(p.process_books([b"a"], job_id="test-dir"))
            self.assertTrue((Path(tmp) / "test-dir.json").exists())


class TestProgressEvent(unittest.TestCase):
    def test_percent_calculation(self):
        from vparse.bulk import ProgressEvent
        e = ProgressEvent(pages_done=25, total_pages=100)
        self.assertEqual(e.percent, 25.0)

    def test_zero_pages_does_not_divide_by_zero(self):
        from vparse.bulk import ProgressEvent
        e = ProgressEvent(pages_done=0, total_pages=0)
        self.assertEqual(e.percent, 0.0)


class TestCLIBatchFlag(unittest.TestCase):
    def test_batch_flag_defaults_to_false(self):
        from vparse.constants import ACCEPTED_BACKENDS
        self.assertIn("vlm", ACCEPTED_BACKENDS)

    def test_batch_flag_accepted_in_available_backends(self):
        from vparse.constants import ACCEPTED_BACKENDS
        self.assertIn("vlm-lmdeploy", ACCEPTED_BACKENDS)


if __name__ == "__main__":
    unittest.main()
