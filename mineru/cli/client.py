# Copyright (c) Opendatalab. All rights reserved.
import json
import os
import time
import sys

import click
from pathlib import Path
from loguru import logger

log_level = os.getenv("MINERU_LOG_LEVEL", "INFO").upper()
logger.remove()  # 移除默认handler
logger.add(sys.stderr, level=log_level)  # 添加新handler

from mineru.utils.cli_parser import arg_parse
from mineru.utils.config_reader import get_device
from mineru.utils.guess_suffix_or_lang import guess_suffix_by_path
from mineru.utils.model_utils import get_vram
from ..version import __version__
from .common import do_parse, read_fn, pdf_suffixes, image_suffixes


def get_checkpoint_path(output_dir: str, input_folder_name: str) -> Path:
    checkpoint_dir = Path(output_dir) / ".mineru_checkpoints"
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
    type=click.Choice(
        [
            "pipeline",
            "vlm-http-client",
            "hybrid-http-client",
            "vlm-auto-engine",
            "hybrid-auto-engine",
        ]
    ),
    help="""\b
    the backend for parsing pdf:
      pipeline: More general.
      vlm-auto-engine: High accuracy via local computing power (uses dots.ocr).
      vlm-http-client: High accuracy via remote computing power (client suitable for openai-compatible servers).
      hybrid-auto-engine: Next-generation high accuracy solution via local computing power (uses dots.ocr for layout).
      hybrid-http-client: High accuracy but requires a little local computing power (client suitable for openai-compatible servers).
    Without method specified, vlm-auto-engine will be used by default.""",
    default="vlm-auto-engine",
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
    When the backend is `<vlm/hybrid>-http-client`, you need to specify the server_url, for example:`http://127.0.0.1:30000`
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
    "--resume/--no-resume",
    "resume",
    help="Resume from checkpoint if previously interrupted. Default is False (disabled).",
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
    resume,
    **kwargs,
):

    kwargs.update(arg_parse(ctx))

    if not backend.endswith("-client"):

        def get_device_mode() -> str:
            if device_mode is not None:
                return device_mode
            else:
                return get_device()

        if os.getenv("MINERU_DEVICE_MODE", None) is None:
            os.environ["MINERU_DEVICE_MODE"] = get_device_mode()

        def get_virtual_vram_size() -> int:
            if virtual_vram is not None:
                return virtual_vram
            else:
                return get_vram(get_device_mode())

        if os.getenv("MINERU_VIRTUAL_VRAM_SIZE", None) is None:
            os.environ["MINERU_VIRTUAL_VRAM_SIZE"] = str(get_virtual_vram_size())

        if os.getenv("MINERU_MODEL_SOURCE", None) is None:
            os.environ["MINERU_MODEL_SOURCE"] = model_source

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
            
            if resume and checkpoint_path.exists():
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

            batch_data = []
            for path in batch_paths:
                file_name = str(Path(path).stem)
                pdf_bytes = read_fn(path)
                batch_data.append((path, file_name, pdf_bytes))

            for path, file_name, pdf_bytes in batch_data:
                try:
                    do_parse(
                        output_dir=output_dir,
                        pdf_file_names=[file_name],
                        pdf_bytes_list=[pdf_bytes],
                        p_lang_list=[lang],
                        backend=backend,
                        parse_method=method,
                        formula_enable=formula_enable,
                        table_enable=table_enable,
                        server_url=server_url,
                        start_page_id=start_page_id,
                        end_page_id=end_page_id,
                        **kwargs,
                    )

                    checkpoint["processed"].append(path.name)

                    if checkpoint_path:
                        checkpoint["total"] = total_files
                        checkpoint["batch_size"] = batch_size
                        save_checkpoint(checkpoint_path, checkpoint)

                    current_processed = len(checkpoint["processed"])
                    logger.info(
                        f"Progress: {current_processed}/{total_files} files processed"
                    )

                except Exception as e:
                    logger.error(f"Error processing {path.name}: {e}")
                    checkpoint["failed"].append(path.name)
                    if checkpoint_path:
                        checkpoint["total"] = total_files
                        checkpoint["batch_size"] = batch_size
                        save_checkpoint(checkpoint_path, checkpoint)
                    logger.info(f"Skipping failed file: {path.name}")
                    continue

    def parse_doc(path_list: list[Path]):
        try:
            file_name_list = []
            pdf_bytes_list = []
            lang_list = []
            for path in path_list:
                file_name = str(Path(path).stem)
                pdf_bytes = read_fn(path)
                file_name_list.append(file_name)
                pdf_bytes_list.append(pdf_bytes)
                lang_list.append(lang)
            do_parse(
                output_dir=output_dir,
                pdf_file_names=file_name_list,
                pdf_bytes_list=pdf_bytes_list,
                p_lang_list=lang_list,
                backend=backend,
                parse_method=method,
                formula_enable=formula_enable,
                table_enable=table_enable,
                server_url=server_url,
                start_page_id=start_page_id,
                end_page_id=end_page_id,
                **kwargs,
            )
        except Exception as e:
            logger.exception(e)

    if os.path.isdir(input_path):
        # Fast file scanning - just check extension, don't read file content
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
        
        input_folder_name = Path(input_path).stem
        parse_doc_with_batching(doc_path_list, input_folder_name)
    else:
        parse_doc([Path(input_path)])


if __name__ == "__main__":
    main()
