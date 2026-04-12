import json
import shutil
import time
from pathlib import Path
from typing import Callable

import pypdfium2 as pdfium

from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, do_parse
from mineru.utils.draw_bbox import draw_layout_bbox


STREAM_DIR_NAME = "stream_preview"


def get_stream_env_name(backend: str, parse_method: str) -> str:
    if backend.startswith("vlm-"):
        return "vlm"
    if backend.startswith("hybrid-"):
        return f"hybrid_{parse_method}"
    return parse_method


def get_final_parse_dir(output_dir, pdf_file_name: str, backend: str, parse_method: str) -> str:
    env_name = get_stream_env_name(backend, parse_method)
    return str(Path(output_dir) / pdf_file_name / env_name)


def cleanup_stream_session(session_root: str | None):
    if not session_root:
        return
    session_path = Path(session_root)
    stream_root = session_path.parent
    if session_path.exists():
        shutil.rmtree(session_path, ignore_errors=True)
    if stream_root.exists() and not any(stream_root.iterdir()):
        stream_root.rmdir()


def _make_empty_page_info(page_index: int) -> dict:
    return {
        "page_idx": page_index,
        "page_size": [0, 0],
        "para_blocks": [],
        "discarded_blocks": [],
        "preproc_blocks": [],
    }


def iter_stream_parse(
    output_dir,
    pdf_file_name: str,
    pdf_bytes: bytes,
    lang: str,
    backend: str,
    parse_method: str,
    formula_enable: bool = True,
    table_enable: bool = True,
    server_url: str | None = None,
    start_page_id: int = 0,
    end_page_id: int | None = None,
    **kwargs,
):
    prepared_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(
        pdf_bytes, start_page_id, end_page_id
    )

    prepared_pdf = pdfium.PdfDocument(prepared_pdf_bytes)
    try:
        total_pages = len(prepared_pdf)
    finally:
        prepared_pdf.close()

    env_name = get_stream_env_name(backend, parse_method)
    session_id = time.strftime("%Y%m%d_%H%M%S")
    session_root = (
        Path(output_dir)
        / pdf_file_name
        / env_name
        / STREAM_DIR_NAME
        / session_id
    )
    pages_root = session_root / "pages"
    shared_images_dir = session_root / "images"
    session_root.mkdir(parents=True, exist_ok=True)
    pages_root.mkdir(parents=True, exist_ok=True)
    shared_images_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = session_root / "stream_state.json"
    preview_md_path = session_root / f"{pdf_file_name}_preview.md"
    preview_middle_path = session_root / f"{pdf_file_name}_preview_middle.json"
    preview_model_path = session_root / f"{pdf_file_name}_preview_model.json"
    preview_content_list_path = session_root / f"{pdf_file_name}_preview_content_list.json"
    preview_content_list_v2_path = (
        session_root / f"{pdf_file_name}_preview_content_list_v2.json"
    )
    preview_pdf_path = session_root / f"{pdf_file_name}_preview.pdf"

    backend_label = "pipeline" if backend == "pipeline" else "vlm"
    preview_middle = {"pdf_info": [], "_backend": backend_label}
    padded_preview_middle = {
        "pdf_info": [_make_empty_page_info(i) for i in range(total_pages)],
        "_backend": backend_label,
    }
    preview_model: list = []
    preview_content_list: list = []
    preview_content_list_v2: list = []
    page_markdown_parts: list[str] = []

    def write_manifest(status: str, completed_pages: int, error: str | None = None):
        payload = {
            "status": status,
            "complete": status == "completed",
            "pdf_file_name": pdf_file_name,
            "backend": backend,
            "parse_method": parse_method,
            "completed_pages": completed_pages,
            "total_pages": total_pages,
            "session_root": str(session_root),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if error is not None:
            payload["error"] = error
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    write_manifest("running", 0)

    try:
        for page_index in range(total_pages):
            page_file_name = f"{pdf_file_name}_page_{page_index + 1:04d}"
            page_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(
                prepared_pdf_bytes, page_index, page_index
            )

            do_parse(
                output_dir=str(pages_root),
                pdf_file_names=[page_file_name],
                pdf_bytes_list=[page_pdf_bytes],
                p_lang_list=[lang],
                backend=backend,
                parse_method=parse_method,
                formula_enable=formula_enable,
                table_enable=table_enable,
                server_url=server_url,
                **kwargs,
            )

            page_dir = pages_root / page_file_name / env_name
            page_images_dir = page_dir / "images"

            if page_images_dir.exists():
                for image_file in page_images_dir.iterdir():
                    if image_file.is_file():
                        shutil.copy2(image_file, shared_images_dir / image_file.name)

            page_md_path = page_dir / f"{page_file_name}.md"
            if page_md_path.exists():
                page_markdown_parts.append(page_md_path.read_text(encoding="utf-8"))
            preview_md_path.write_text(
                "\n\n".join(page_markdown_parts).strip() + ("\n" if page_markdown_parts else ""),
                encoding="utf-8",
            )

            page_middle_path = page_dir / f"{page_file_name}_middle.json"
            page_middle = json.loads(page_middle_path.read_text(encoding="utf-8"))
            preview_middle["_version_name"] = page_middle.get("_version_name")
            for page_info in page_middle.get("pdf_info", []):
                page_info["page_idx"] = page_index
                preview_middle["pdf_info"].append(page_info)
                padded_preview_middle["pdf_info"][page_index] = page_info
            preview_middle_path.write_text(
                json.dumps(preview_middle, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            draw_layout_bbox(
                padded_preview_middle["pdf_info"],
                prepared_pdf_bytes,
                str(session_root),
                f"{pdf_file_name}_preview.pdf",
            )

            page_model_path = page_dir / f"{page_file_name}_model.json"
            page_model = json.loads(page_model_path.read_text(encoding="utf-8"))
            if backend == "pipeline":
                for model_page in page_model:
                    if "page_info" in model_page:
                        model_page["page_info"]["page_no"] = page_index
                preview_model.extend(page_model)
            else:
                preview_model.extend(page_model)
            preview_model_path.write_text(
                json.dumps(preview_model, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )

            page_content_list_path = page_dir / f"{page_file_name}_content_list.json"
            page_content_list = json.loads(
                page_content_list_path.read_text(encoding="utf-8")
            )
            for item in page_content_list:
                item["page_idx"] = page_index
                preview_content_list.append(item)
            preview_content_list_path.write_text(
                json.dumps(preview_content_list, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )

            page_content_list_v2_path = page_dir / f"{page_file_name}_content_list_v2.json"
            if page_content_list_v2_path.exists():
                page_content_list_v2 = json.loads(
                    page_content_list_v2_path.read_text(encoding="utf-8")
                )
                for item in page_content_list_v2:
                    item["page_idx"] = page_index
                    preview_content_list_v2.append(item)
                preview_content_list_v2_path.write_text(
                    json.dumps(preview_content_list_v2, ensure_ascii=False, indent=4),
                    encoding="utf-8",
                )

            current_layout_pdf = page_dir / f"{page_file_name}_layout.pdf"
            write_manifest("running", page_index + 1)

            yield {
                "page_index": page_index,
                "completed_pages": page_index + 1,
                "total_pages": total_pages,
                "session_root": str(session_root),
                "preview_md_path": str(preview_md_path),
                "preview_middle_path": str(preview_middle_path),
                "preview_pdf_path": str(preview_pdf_path) if preview_pdf_path.exists() else None,
                "preview_model_path": str(preview_model_path),
                "preview_content_list_path": str(preview_content_list_path),
                "preview_content_list_v2_path": (
                    str(preview_content_list_v2_path)
                    if preview_content_list_v2_path.exists()
                    else None
                ),
                "preview_md": preview_md_path.read_text(encoding="utf-8"),
                "current_layout_pdf": (
                    str(preview_pdf_path) if preview_pdf_path.exists()
                    else (str(current_layout_pdf) if current_layout_pdf.exists() else None)
                ),
                "manifest_path": str(manifest_path),
            }

        write_manifest("completed", total_pages)
    except Exception as exc:
        write_manifest("failed", len(preview_middle["pdf_info"]), str(exc))
        raise


def stream_parse(
    output_dir,
    pdf_file_name: str,
    pdf_bytes: bytes,
    lang: str,
    backend: str,
    parse_method: str,
    formula_enable: bool = True,
    table_enable: bool = True,
    server_url: str | None = None,
    start_page_id: int = 0,
    end_page_id: int | None = None,
    page_callback: Callable[[dict], None] | None = None,
    **kwargs,
) -> str:
    session_root = None
    write_manifest = None
    for update in iter_stream_parse(
        output_dir=output_dir,
        pdf_file_name=pdf_file_name,
        pdf_bytes=pdf_bytes,
        lang=lang,
        backend=backend,
        parse_method=parse_method,
        formula_enable=formula_enable,
        table_enable=table_enable,
        server_url=server_url,
        start_page_id=start_page_id,
        end_page_id=end_page_id,
        **kwargs,
    ):
        session_root = update["session_root"]
        write_manifest = update["manifest_path"]
        if page_callback is not None:
            page_callback(update)

    do_parse(
        output_dir=output_dir,
        pdf_file_names=[pdf_file_name],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=[lang],
        backend=backend,
        parse_method=parse_method,
        formula_enable=formula_enable,
        table_enable=table_enable,
        server_url=server_url,
        f_draw_layout_bbox=True,
        f_draw_span_bbox=True,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=True,
        f_dump_orig_pdf=True,
        f_dump_content_list=True,
        start_page_id=start_page_id,
        end_page_id=end_page_id,
        **kwargs,
    )

    if write_manifest is not None:
        manifest_path = Path(write_manifest)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "completed"
        manifest["complete"] = True
        manifest["final_parse_dir"] = get_final_parse_dir(
            output_dir, pdf_file_name, backend, parse_method
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    cleanup_stream_session(session_root)
    return session_root
