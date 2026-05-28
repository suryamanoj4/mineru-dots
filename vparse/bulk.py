from __future__ import annotations

import asyncio
import gc
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from vparse.data.data_reader_writer import DataWriter
from vparse.cli.common import read_fn


@dataclass
class ProgressEvent:
    completed_books: int = 0
    total_books: int = 0
    pages_done: int = 0
    total_pages: int = 0
    elapsed_seconds: float = 0.0
    pages_per_sec: float = 0.0
    eta_seconds: float = 0.0

    @property
    def percent(self) -> float:
        if self.total_pages:
            return self.pages_done / self.total_pages * 100
        return 0.0


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass
class JobResult:
    book_index: int
    middle_json: dict[str, Any]
    model_output: list[Any]


class BulkProcessor:
    def __init__(
        self,
        page_batch_size: int = 0,
        checkpoint_dir: str | Path | None = None,
    ):
        self.checkpoint_dir = Path(checkpoint_dir or ".vparse_checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.page_batch_size = page_batch_size
        self._start_time: float = 0.0
        self._completed_pages = 0
        self._total_pages_est = 0

    def _checkpoint_path(self, job_id: str) -> Path:
        return self.checkpoint_dir / f"{job_id}.json"

    def _load_checkpoint(self, job_id: str) -> tuple[set[int], set[int]]:
        path = self._checkpoint_path(job_id)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return set(data.get("done", [])), set(data.get("failed", []))
        return set(), set()

    def _save_checkpoint(self, job_id: str, done: set[int], failed: set[int] | None = None) -> None:
        path = self._checkpoint_path(job_id)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump({"done": sorted(done), "failed": sorted(failed) if failed else []}, f)
        tmp.replace(path)

    def _estimate_total_pages(self, pdf_bytes_list: list[bytes] | list[Path]) -> int:
        import pypdfium2 as pdfium
        total = 0
        for item in pdf_bytes_list:
            try:
                if isinstance(item, Path):
                    doc = pdfium.PdfDocument(str(item))
                else:
                    doc = pdfium.PdfDocument(item)
                total += len(doc)
                doc.close()
            except Exception:
                total += 10
        return max(total, 1)

    async def process_books(
        self,
        pdf_bytes_list: list[bytes] | list[Path],
        image_writers: list[DataWriter | None] | None = None,
        job_id: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_result: Callable[[JobResult], Awaitable[None]] | None = None,
        chunk_size: int = 10,
        **kwargs,
    ) -> list[JobResult]:
        job_id = job_id or f"bulk_{int(time.time())}"
        done_set, failed_set = self._load_checkpoint(job_id)

        excluded = done_set | failed_set
        remaining_indices = [
            i for i in range(len(pdf_bytes_list)) if i not in excluded
        ]

        if excluded:
            parts = []
            if done_set:
                parts.append(f"{len(done_set)} already processed")
            if failed_set:
                parts.append(f"{len(failed_set)} failed")
            logger.info(
                f"Resuming: {', '.join(parts)}, "
                f"{len(remaining_indices)} remaining"
            )

        if not remaining_indices:
            return []

        self._start_time = time.time()
        self._completed_pages = 0

        if image_writers and len(image_writers) != len(pdf_bytes_list):
            raise ValueError(
                "image_writers length must match pdf_bytes_list"
            )

        total_pages = self._estimate_total_pages(pdf_bytes_list)
        self._total_pages_est = total_pages
        logger.info(f"Estimated {total_pages} pages across {len(pdf_bytes_list)} docs, {len(remaining_indices)} remaining")

        backend_name = kwargs.pop("backend", "vlm")
        engine = kwargs.pop("engine", None)

        if engine == "lmdeploy":
            backend_name = "lmdeploy"
        elif backend_name in ("vlm", "hybrid"):
            from vparse.backend.vlm.utils import resolve_vlm_engine
            backend_name = resolve_vlm_engine()
        elif backend_name.endswith("-lmdeploy"):
            backend_name = "lmdeploy"

        all_results = [] if on_result is None else None

        # Process in chunks to ensure checkpoints are saved incrementally and memory is saved
        for i in range(0, len(remaining_indices), chunk_size):
            chunk_indices = remaining_indices[i:i+chunk_size]
            
            # Lazy load bytes only for the current chunk, skipping unreadable files
            chunk_bytes = []
            good_indices = []
            for idx in chunk_indices:
                item = pdf_bytes_list[idx]
                try:
                    pdf_bytes = read_fn(item) if isinstance(item, Path) else item
                    chunk_bytes.append(pdf_bytes)
                    good_indices.append(idx)
                except Exception as e:
                    logger.error(f"Error reading book at index {idx}: {e}")
                    failed_set.add(idx)
                    self._save_checkpoint(job_id, done_set, failed_set)

            if not good_indices:
                continue

            chunk_writers = None
            if image_writers:
                chunk_writers = [image_writers[idx] for idx in good_indices]

            from vparse.backend.vlm.vlm_analyze import _aio_doc_analyze

            tasks = []
            task_info = {}
            for offset, idx in enumerate(good_indices):
                writer = chunk_writers[offset] if chunk_writers else None
                coro = _aio_doc_analyze(
                    chunk_bytes[offset],
                    image_writer=writer,
                    predictor=None,
                    backend=backend_name,
                    **kwargs,
                )
                task = asyncio.create_task(coro)
                task_info[task] = (offset, idx)
                tasks.append(task)

            chunk_pages_done = 0
            pending = set(tasks)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    offset, book_idx = task_info[task]
                    try:
                        mj, mo = await task
                    except Exception as e:
                        logger.error(f"Error processing book {book_idx}: {e}")
                        mj, mo = {}, []

                    jr = JobResult(book_index=book_idx, middle_json=mj, model_output=mo)

                    if on_result:
                        await on_result(jr)
                    else:
                        if all_results is not None:
                            all_results.append(jr)

                    pdf_info = mj.get("pdf_info", [])
                    chunk_pages_done += len(pdf_info)

                    done_set.add(book_idx)
                    self._save_checkpoint(job_id, done_set, failed_set)

            self._completed_pages += chunk_pages_done
            if on_progress:
                elapsed = time.time() - self._start_time
                pps = self._completed_pages / elapsed if elapsed > 0 else 0
                eta = (self._total_pages_est - self._completed_pages) / pps if pps > 0 else 0
                on_progress(ProgressEvent(
                    pages_done=self._completed_pages,
                    total_pages=self._total_pages_est,
                    elapsed_seconds=elapsed,
                    pages_per_sec=pps,
                    eta_seconds=eta,
                ))

            # Explicitly clear memory for the processed chunk
            del chunk_bytes
            if chunk_writers:
                del chunk_writers
            gc.collect()

        return all_results if all_results is not None else []

    async def process_with_progress(
        self,
        pdf_bytes_list: list[bytes],
        image_writers: list[DataWriter | None] | None = None,
        job_id: str | None = None,
        on_progress: ProgressCallback | None = None,
        **kwargs,
    ) -> list[JobResult]:
        return await self.process_books(
            pdf_bytes_list,
            image_writers=image_writers,
            job_id=job_id,
            on_progress=on_progress,
            **kwargs,
        )
