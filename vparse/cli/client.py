# Copyright (c) Opendatalab. All rights reserved.
import gc
import json
import os
import time
import sys
import asyncio

import click
from pathlib import Path
from loguru import logger
from vparse import VParse
from vparse.constants import ACCEPTED_BACKENDS, AVAILABLE_BACKENDS
from vparse.utils.compat import get_env_with_legacy

log_level = get_env_with_legacy("VPARSE_LOG_LEVEL", "MINERU_LOG_LEVEL", "INFO").upper()
logger.remove()  # Remove default handler
logger.add(sys.stderr, level=log_level)  # Add new handler

from vparse.utils.cli_parser import arg_parse
from vparse.utils.config_reader import get_device
from vparse.utils.guess_suffix_or_lang import guess_suffix_by_path
from vparse.utils.model_utils import get_vram
from ..version import __version__
from .common import do_parse, read_fn, pdf_suffixes, image_suffixes, _process_output, prepare_env
from .streaming import stream_parse

CLI_DRAW_LAYOUT_BBOX = True
CLI_DRAW_SPAN_BBOX = False
CLI_DUMP_MD = True
CLI_DUMP_CONTENT_LIST = True
CLI_DUMP_MIDDLE_JSON = False
CLI_DUMP_MODEL_OUTPUT = False
CLI_DUMP_ORIG_PDF = False


def get_checkpoint_path(output_dir: str, input_folder_name: str) -> Path:
    checkpoint_dir = Path(output_dir) / ".vparse_checkpoints"
    return checkpoint_dir / f"{input_folder_name}.json"


def load_checkpoint(checkpoint_path: Path) -> dict:
    if checkpoint_path.exists():
        with open(checkpoint_path, "r") as f:
            return json.load(f)
    return {"processed": [], "total": 0, "batch_size": 20}


def save_checkpoint(checkpoint_path: Path, checkpoint: dict):
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f, indent=2)


def build_vparse_client(
    backend: str,
    lang: str,
    device_mode: str | None,
    formula_enable: bool,
    table_enable: bool,
    server_url: str | None,
    start_page_id: int,
    end_page_id: int | None,
    extra_kwargs: dict,
) -> VParse:
    constructor_kwargs = dict(extra_kwargs)
    constructor_kwargs.update(
        {
            "server_url": server_url,
            "start_page_id": start_page_id,
            "end_page_id": end_page_id,
        }
    )
    return VParse(
        backend=backend,
        lang=lang,
        device=device_mode,
        formula_enable=formula_enable,
        table_enable=table_enable,
        **constructor_kwargs,
    )


@click.command(
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
)
@click.pass_context
@click.version_option(
    __version__, "--version", "-v", help="display the version and exit"
)
@click.option(
    "-p",
    "--path",
    "input_path",
    type=click.Path(exists=True),
    required=True,
    help="local filepath or directory. support pdf, png, jpg, jpeg files",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(),
    required=True,
    help="output local directory",
)
@click.option(
    "-m",
    "--method",
    "method",
    type=click.Choice(["auto", "txt", "ocr"]),
    help="""\b
    the method for parsing pdf:
      auto: Automatically determine the method based on the file type.
      txt: Use text extraction method.
      ocr: Use OCR method for image-based PDFs.
    Without method specified, 'auto' will be used by default.
    Adapted only for the case where the backend is set to 'pipeline' and 'hybrid-*'.""",
    default="auto",
)
@click.option(
    "-b",
    "--backend",
    "backend",
    type=click.Choice(list(ACCEPTED_BACKENDS)),
    help="""\b
    the backend for parsing pdf:
      pipeline: Layout detection + PaddleOCR/Tesseract + table/formula extraction.
      lite: Lightweight Tesseract-only backend for CPU fast path.
      vlm: VLM with auto-optimized engine (vLLM for CUDA, MLX for Apple Silicon).
      vlm-lmdeploy: VLM using LMDeploy engine explicitly.
      hybrid: VLM for layout + pipeline OCR, supports multiple languages.
      hybrid-lmdeploy: Hybrid using LMDeploy engine explicitly.
      remote: Point at any OpenAI-compatible server via --server-url.
    Legacy aliases such as vlm-auto-engine and hybrid-auto-engine are also accepted.""",
    default="hybrid",
)
@click.option(
    "-l",
    "--lang",
    "lang",
    type=click.Choice(
        [
            "ch",
            "ch_server",
            "ch_lite",
            "en",
            "korean",
            "japan",
            "chinese_cht",
            "ta",
            "te",
            "ka",
            "th",
            "el",
            "latin",
            "arabic",
            "east_slavic",
            "cyrillic",
            "devanagari",
        ]
    ),
    help="""
    Input the languages in the pdf (if known) to improve OCR accuracy.
    Without languages specified, 'ch' will be used by default.
    Adapted only for the case where the backend is set to 'pipeline' and 'hybrid-*'.
    """,
    default="ch",
)
@click.option(
    "-u",
    "--url",
    "server_url",
    type=str,
    help="""
    When the backend is `remote`, you need to specify the server_url, for example:`http://127.0.0.1:30000`
    """,
    default=None,
)
@click.option(
    "-s",
    "--start",
    "start_page_id",
    type=int,
    help="The starting page for PDF parsing, beginning from 0.",
    default=0,
)
@click.option(
    "-e",
    "--end",
    "end_page_id",
    type=int,
    help="The ending page for PDF parsing, beginning from 0.",
    default=None,
)
@click.option(
    "-f",
    "--formula",
    "formula_enable",
    type=bool,
    help="Enable formula parsing. Default is True. ",
    default=True,
)
@click.option(
    "-t",
    "--table",
    "table_enable",
    type=bool,
    help="Enable table parsing. Default is True. ",
    default=True,
)
@click.option(
    "-d",
    "--device",
    "device_mode",
    type=str,
    help="""Device mode for model inference, e.g., "cpu", "cuda", "cuda:0", "npu", "npu:0", "mps".
         Adapted only for the case where the backend is set to "pipeline". """,
    default=None,
)
@click.option(
    "--vram",
    "virtual_vram",
    type=int,
    help='Upper limit of GPU memory occupied by a single process. Adapted only for the case where the backend is set to "pipeline". ',
    default=None,
)
@click.option(
    "--source",
    "model_source",
    type=click.Choice(["huggingface", "modelscope", "local"]),
    help="""
    The source of the model repository. Default is 'huggingface'.
    """,
    default="huggingface",
)
@click.option(
    "-bs",
    "--batch-size",
    "batch_size",
    type=int,
    help="Number of PDF files to load into RAM at once for batch processing. Default is 20.",
    default=20,
)
@click.option(
    "--stream/--no-stream",
    "stream",
    help="Write staged per-page streaming outputs instead of waiting for the full document to finish.",
    default=False,
)
def main(
    ctx,
    input_path,
    output_dir,
    method,
    backend,
    lang,
    server_url,
    start_page_id,
    end_page_id,
    formula_enable,
    table_enable,
    device_mode,
    virtual_vram,
    model_source,
    batch_size,
    stream,
    **kwargs,
):

    kwargs.update(arg_parse(ctx))

    if backend != "remote":

        def get_device_mode() -> str:
            if device_mode is not None:
                return device_mode
            else:
                return get_device()

        if os.getenv("VPARSE_DEVICE_MODE", None) is None:
            os.environ["VPARSE_DEVICE_MODE"] = get_device_mode()

        def get_virtual_vram_size() -> int:
            if virtual_vram is not None:
                return virtual_vram
            else:
                return get_vram(get_device_mode())

        if os.getenv("VPARSE_VIRTUAL_VRAM_SIZE", None) is None:
            os.environ["VPARSE_VIRTUAL_VRAM_SIZE"] = str(get_virtual_vram_size())

        if os.getenv("VPARSE_MODEL_SOURCE", None) is None:
            os.environ["VPARSE_MODEL_SOURCE"] = model_source

    os.makedirs(output_dir, exist_ok=True)

    def parse_doc_with_batching(
        path_list: list[Path], input_folder_name: str | None = None
    ):
        checkpoint_path = None
        checkpoint = {
            "processed": [],
            "failed": [],
            "total": len(path_list),
            "batch_size": batch_size,
        }

        # Checkpoint is only used for folder input (not single files)
        if input_folder_name:
            checkpoint_path = get_checkpoint_path(output_dir, input_folder_name)
            
            if checkpoint_path.exists():
                # Load existing checkpoint for resume
                checkpoint = load_checkpoint(checkpoint_path)
                if "failed" not in checkpoint:
                    checkpoint["failed"] = []
                logger.info(
                    f"Resuming: {len(checkpoint['processed'])}/{checkpoint['total']} processed, "
                    f"{len(checkpoint['failed'])} failed"
                )
            else:
                # New run - checkpoint will be created on first save
                logger.info(f"Checkpoint file: {checkpoint_path}")

        processed_set = set(checkpoint["processed"])
        failed_set = set(checkpoint.get("failed", []))
        remaining_paths = [
            p
            for p in path_list
            if p.name not in processed_set and p.name not in failed_set
        ]
        total_files = len(path_list)

        if not remaining_paths:
            logger.info("All files already processed!")
            return

        logger.info(
            f"Processing {len(remaining_paths)} of {total_files} files with batch size {batch_size}"
        )

        for batch_start in range(0, len(remaining_paths), batch_size):
            batch_paths = remaining_paths[batch_start : batch_start + batch_size]

            readable_paths = []
            for path in batch_paths:
                try:
                    read_fn(path)
                    readable_paths.append(path)
                except Exception as e:
                    logger.error(f"Error reading {path.name}: {e}")
                    checkpoint["failed"].append(path.name)
                    if checkpoint_path:
                        checkpoint["total"] = total_files
                        checkpoint["batch_size"] = batch_size
                        save_checkpoint(checkpoint_path, checkpoint)
                    logger.info(f"Skipping unreadable file: {path.name}")

            if not readable_paths:
                continue

            try:
                if stream:
                    for path in readable_paths:
                        file_name = str(Path(path).stem)
                        pdf_bytes = read_fn(path)
                        stream_session = stream_parse(
                            output_dir=output_dir,
                            pdf_file_name=file_name,
                            pdf_bytes=pdf_bytes,
                            lang=lang,
                            backend=backend,
                            parse_method=method,
                            formula_enable=formula_enable,
                            table_enable=table_enable,
                            server_url=server_url,
                            start_page_id=start_page_id,
                            end_page_id=end_page_id,
                            page_callback=lambda update, current_path=path: logger.info(
                                f"{current_path.name}: streamed page {update['completed_pages']}/{update['total_pages']}"
                            ),
                            **kwargs,
                        )
                        logger.info(f"Streaming output dir: {stream_session}")
                else:
                    with build_vparse_client(
                        backend=backend,
                        lang=lang,
                        device_mode=device_mode,
                        formula_enable=formula_enable,
                        table_enable=table_enable,
                        server_url=server_url,
                        start_page_id=start_page_id,
                        end_page_id=end_page_id,
                        extra_kwargs=kwargs,
                    ) as client:
                        client.process_batch(
                            readable_paths,
                            output_dir=output_dir,
                            method=method,
                            draw_layout_bbox=CLI_DRAW_LAYOUT_BBOX,
                            draw_span_bbox=CLI_DRAW_SPAN_BBOX,
                            dump_md=CLI_DUMP_MD,
                            dump_content_list=CLI_DUMP_CONTENT_LIST,
                            dump_middle_json=CLI_DUMP_MIDDLE_JSON,
                            dump_model_output=CLI_DUMP_MODEL_OUTPUT,
                            dump_orig_pdf=CLI_DUMP_ORIG_PDF,
                            callback=lambda progress, total, current_batch=readable_paths: logger.info(
                                f"Batch progress: {progress}/{total} files ({current_batch[progress - 1].name})"
                            ),
                        )

                checkpoint["processed"].extend(path.name for path in readable_paths)

                if checkpoint_path:
                    checkpoint["total"] = total_files
                    checkpoint["batch_size"] = batch_size
                    save_checkpoint(checkpoint_path, checkpoint)

                current_processed = len(checkpoint["processed"])
                logger.info(
                    f"Progress: {current_processed}/{total_files} files processed"
                )
            except Exception as e:
                logger.error(f"Error processing batch starting with {readable_paths[0].name}: {e}")
                checkpoint["failed"].extend(
                    path.name
                    for path in readable_paths
                    if path.name not in checkpoint["failed"]
                )
                if checkpoint_path:
                    checkpoint["total"] = total_files
                    checkpoint["batch_size"] = batch_size
                    save_checkpoint(checkpoint_path, checkpoint)
                logger.info("Skipping failed batch")
                continue

    def parse_doc(path_list: list[Path]):
        try:
            if stream:
                for path in path_list:
                    file_name = str(Path(path).stem)
                    pdf_bytes = read_fn(path)
                    stream_session = stream_parse(
                        output_dir=output_dir,
                        pdf_file_name=file_name,
                        pdf_bytes=pdf_bytes,
                        lang=lang,
                        backend=backend,
                        parse_method=method,
                        formula_enable=formula_enable,
                        table_enable=table_enable,
                        server_url=server_url,
                        start_page_id=start_page_id,
                        end_page_id=end_page_id,
                        page_callback=lambda update, current_path=path: logger.info(
                            f"{current_path.name}: streamed page {update['completed_pages']}/{update['total_pages']}"
                        ),
                        **kwargs,
                    )
                    logger.info(f"Streaming output dir: {stream_session}")
            else:
                with build_vparse_client(
                    backend=backend,
                    lang=lang,
                    device_mode=device_mode,
                    formula_enable=formula_enable,
                    table_enable=table_enable,
                    server_url=server_url,
                    start_page_id=start_page_id,
                    end_page_id=end_page_id,
                    extra_kwargs=kwargs,
                ) as client:
                    client.process_batch(
                        path_list,
                        output_dir=output_dir,
                        method=method,
                        draw_layout_bbox=CLI_DRAW_LAYOUT_BBOX,
                        draw_span_bbox=CLI_DRAW_SPAN_BBOX,
                        dump_md=CLI_DUMP_MD,
                        dump_content_list=CLI_DUMP_CONTENT_LIST,
                        dump_middle_json=CLI_DUMP_MIDDLE_JSON,
                        dump_model_output=CLI_DUMP_MODEL_OUTPUT,
                        dump_orig_pdf=CLI_DUMP_ORIG_PDF,
                    )
        except Exception as e:
            logger.exception(e)

    async def _run_batch(path_list: list[Path]):
        from vparse.backend.registry import BackendRegistry, resolve_backend_name
        from vparse.data.data_reader_writer import FileBasedDataWriter
        from vparse.utils.enum_class import MakeMode

        resolved = resolve_backend_name(backend)
        is_lmdeploy = resolved == "vlm-lmdeploy"

        logger.info(f"Batch processing {len(path_list)} files via {resolved}")

        # Derive file names and track load errors lazily
        file_names = {i: path.stem for i, path in enumerate(path_list)}
        
        last_progress = 0
        def on_progress(e):
            nonlocal last_progress
            if e.pages_done - last_progress >= 10 or e.pages_done == e.total_pages:
                logger.info(
                    f"batch progress: {e.pages_done}/{e.total_pages} pages "
                    f"({e.pages_per_sec:.1f} p/s, ETA {e.eta_seconds:.0f}s)"
                )
                last_progress = e.pages_done

        kwargs.pop("engine", None)
        if is_lmdeploy:
            kwargs["engine"] = "lmdeploy"

        from vparse.bulk import BulkProcessor

        output_subdir = "vlm"
        if resolved.startswith("hybrid"):
            output_subdir = f"hybrid_{method}"

        async def on_result(result):
            book_idx = result.book_index
            file_name = file_names[book_idx]
            path = path_list[book_idx]
            try:
                pdf_bytes = read_fn(path)
            except Exception as e:
                logger.error(f"Failed to read {path.name}: {e}")
                return

            local_image_dir, local_md_dir = prepare_env(
                output_dir, file_name, output_subdir
            )
            md_writer = FileBasedDataWriter(local_md_dir)
            pdf_info = result.middle_json.get("pdf_info", [])

            _process_output(
                pdf_info, pdf_bytes, file_name, local_md_dir, local_image_dir,
                md_writer, CLI_DRAW_LAYOUT_BBOX, CLI_DRAW_SPAN_BBOX,
                CLI_DUMP_ORIG_PDF, CLI_DUMP_MD, CLI_DUMP_CONTENT_LIST,
                CLI_DUMP_MIDDLE_JSON, CLI_DUMP_MODEL_OUTPUT,
                MakeMode.MM_MD, result.middle_json, result.model_output,
                is_pipeline=False,
            )
            del pdf_bytes
            gc.collect()

        # Move legacy .mineru_checkpoints checkpoint to new location
        checkpoints_dir = Path(output_dir) / ".vparse_checkpoints"
        job_id = Path(input_path).stem
        legacy_dir = Path(output_dir) / ".mineru_checkpoints"
        legacy_file = legacy_dir / f"{job_id}.json"
        new_checkpoint = checkpoints_dir / f"{job_id}.json"
        if legacy_file.exists() and not new_checkpoint.exists():
            checkpoints_dir.mkdir(parents=True, exist_ok=True)
            legacy_file.rename(new_checkpoint)
            try:
                legacy_dir.rmdir()
            except OSError:
                pass
            with open(new_checkpoint) as f:
                data = json.load(f)
            processed = len(data.get("processed", []))
            failed = len(data.get("failed", []))
            parts = []
            if processed:
                parts.append(f"{processed} already processed")
            if failed:
                parts.append(f"{failed} failed")
            logger.info(f"Migrated legacy checkpoint: {', '.join(parts)}")

        proc = BulkProcessor(checkpoint_dir=checkpoints_dir)
        logger.info("Starting bulk processing with chunk_size=10")
        try:
            await proc.process_books(
                path_list,
                job_id=job_id,
                on_progress=on_progress,
                on_result=on_result,
                backend=resolved,
                **kwargs,
            )
        except Exception as e:
            logger.exception(f"Batch processing failed: {e}")
            raise

    if os.path.isdir(input_path):
        doc_path_list = []
        pdf_extensions = {'.pdf'}
        image_extensions = {'.png', '.jpeg', '.jpg', '.jp2', '.webp', '.gif', '.bmp', '.tiff'}
        valid_extensions = pdf_extensions | image_extensions
        
        logger.info(f"Scanning directory: {input_path}")
        scan_start = time.time()
        
        for doc_path in Path(input_path).glob("*"):
            if doc_path.suffix.lower() in valid_extensions and doc_path.is_file():
                doc_path_list.append(doc_path)
        
        scan_time = round(time.time() - scan_start, 2)
        logger.info(f"Found {len(doc_path_list)} files in {scan_time}s")

        from vparse.backend.registry import resolve_backend_name
        resolved_backend = resolve_backend_name(backend)
        is_vlm_hybrid = (
            resolved_backend.startswith("vlm") or resolved_backend.startswith("hybrid")
        )

        if is_vlm_hybrid and len(doc_path_list) > 1:
            asyncio.run(_run_batch(doc_path_list))
        else:
            input_folder_name = Path(input_path).stem
            parse_doc_with_batching(doc_path_list, input_folder_name)
    else:
        parse_doc([Path(input_path)])


if __name__ == "__main__":
    main()
