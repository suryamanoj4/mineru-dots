"""FastMCP server for the MinerU file-to-Markdown service."""

import json
import re
import traceback
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

import aiohttp
import uvicorn
from fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from pydantic import Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from . import config
from .api import MinerUClient
from .language import get_language_list

mcp = FastMCP(
    name="MinerU File to Markdown Conversion",
    instructions="""
    Convert documents into Markdown, JSON, and related formats.
    Supported inputs include PDF, Word, PowerPoint, and common image formats.

    Tools:
    parse_documents: Parse local files or URLs and return extracted content.
    get_ocr_languages: Return the OCR languages supported by MinerU.
    """,
)

_client_instance: Optional[MinerUClient] = None


def create_starlette_app(mcp_server, *, debug: bool = False) -> Starlette:
    """Create the Starlette app used for SSE transport."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle an SSE connection."""
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


def run_server(mode=None, port=8001, host="127.0.0.1"):
    """Run the FastMCP server."""
    config.ensure_output_dir(output_dir)

    if not config.MINERU_API_KEY:
        config.logger.warning("MINERU_API_KEY is not set.")
        config.logger.warning("Set it with: export MINERU_API_KEY=your_api_key")

    mcp_server = mcp._mcp_server

    try:
        if mode == "sse":
            config.logger.info(f"Starting SSE server on {host}:{port}")
            starlette_app = create_starlette_app(mcp_server, debug=True)
            uvicorn.run(starlette_app, host=host, port=port)
        elif mode == "streamable-http":
            config.logger.info(f"Starting streamable HTTP server on {host}:{port}")
            mcp.run(mode, port=port)
        else:
            config.logger.info("Starting STDIO server")
            mcp.run(mode or "stdio")
    except Exception as e:
        config.logger.error(f"\nService exited with an error: {str(e)}")
        traceback.print_exc()
    finally:
        cleanup_resources()


def cleanup_resources():
    """Release global resources before shutdown."""
    global _client_instance
    if _client_instance is not None:
        try:
            if hasattr(_client_instance, "close"):
                _client_instance.close()
        except Exception as e:
            config.logger.error(f"Error while cleaning up client resources: {str(e)}")
        finally:
            _client_instance = None
    config.logger.info("Resource cleanup complete")


def get_client() -> MinerUClient:
    """Return the shared MinerU client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = MinerUClient()  # Initialization happens here
    return _client_instance


output_dir = config.DEFAULT_OUTPUT_DIR


def set_output_dir(dir_path: str):
    """Update the output directory for converted files."""
    global output_dir
    output_dir = dir_path
    config.ensure_output_dir(output_dir)
    return output_dir


def parse_list_input(input_str: str) -> List[str]:
    """Split a string containing comma- or newline-separated items."""
    if not input_str:
        return []

    items = re.split(r"[,\n\s]+", input_str)

    result = []
    for item in items:
        item = item.strip()
        if (item.startswith('"') and item.endswith('"')) or (
            item.startswith("'") and item.endswith("'")
        ):
            item = item[1:-1]

        if item:
            result.append(item)

    return result


async def convert_file_url(
    url: str,
    enable_ocr: bool = False,
    language: str = "ch",
    page_ranges: str | None = None,
) -> Dict[str, Any]:
    """Convert one or more URLs to Markdown."""
    urls_to_process = None

    if isinstance(url, dict):
        urls_to_process = url
    elif isinstance(url, list) and len(url) > 0 and isinstance(url[0], dict):
        urls_to_process = url
    elif isinstance(url, str):
        if url.strip().startswith("[") and url.strip().endswith("]"):
            try:
                url_configs = json.loads(url)
                if not isinstance(url_configs, list):
                    raise ValueError("JSON URL config must be a list")

                urls_to_process = url_configs
            except json.JSONDecodeError:
                pass

    if urls_to_process is None:
        urls = parse_list_input(url)

        if not urls:
            raise ValueError("No valid URL provided")

        if len(urls) == 1:
            urls_to_process = {"url": urls[0], "is_ocr": enable_ocr}
        else:
            urls_to_process = []
            for url_item in urls:
                urls_to_process.append(
                    {
                        "url": url_item,
                        "is_ocr": enable_ocr,
                    }
                )

    try:
        result_path = await get_client().process_file_to_markdown(
            lambda urls, o: get_client().submit_file_url_task(
                urls,
                o,
                language=language,
                page_ranges=page_ranges,
            ),
            urls_to_process,
            enable_ocr,
            output_dir,
        )
        return {"status": "success", "result_path": result_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def convert_file_path(
    file_path: str,
    enable_ocr: bool = False,
    language: str = "ch",
    page_ranges: str | None = None,
) -> Dict[str, Any]:
    """Convert one or more local files to Markdown."""

    files_to_process = None

    if isinstance(file_path, dict):
        files_to_process = file_path
    elif (
        isinstance(file_path, list)
        and len(file_path) > 0
        and isinstance(file_path[0], dict)
    ):
        files_to_process = file_path
    elif isinstance(file_path, str):
        if file_path.strip().startswith("[") and file_path.strip().endswith("]"):
            try:
                file_configs = json.loads(file_path)
                if not isinstance(file_configs, list):
                    raise ValueError("JSON file config must be a list")

                files_to_process = file_configs
            except json.JSONDecodeError:
                pass

    if files_to_process is None:
        file_paths = parse_list_input(file_path)

        if not file_paths:
            raise ValueError("No valid file path provided")

        if len(file_paths) == 1:
            files_to_process = {
                "path": file_paths[0],
                "is_ocr": enable_ocr,
            }
        else:
            files_to_process = []
            for path in file_paths:
                files_to_process.append(
                    {
                        "path": path,
                        "is_ocr": enable_ocr,
                    }
                )

    try:
        result_path = await get_client().process_file_to_markdown(
            lambda files, o: get_client().submit_file_task(
                files,
                o,
                language=language,
                page_ranges=page_ranges,
            ),
            files_to_process,
            enable_ocr,
            output_dir,
        )
        return {"status": "success", "result_path": result_path}
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "params": {
                "file_path": file_path,
                "enable_ocr": enable_ocr,
                "language": language,
            },
        }


async def local_parse_file(
    file_path: str,
    parse_method: str = "auto",
) -> Dict[str, Any]:
    """Parse a local file via the configured local API."""
    file_path = Path(file_path)

    if not file_path.exists():
        return {"status": "error", "error": f"File does not exist: {file_path}"}

    try:
        if config.USE_LOCAL_API:
            config.logger.debug(f"Using local API: {config.LOCAL_MINERU_API_BASE}")
            return await _parse_file_local(
                file_path=str(file_path),
                parse_method=parse_method,
            )
        else:
            return {"status": "error", "error": "Remote API is not configured"}
    except Exception as e:
        config.logger.error(f"Error while parsing file: {str(e)}")
        return {"status": "error", "error": str(e)}


async def read_converted_file(
    file_path: str,
) -> Dict[str, Any]:
    """Read a converted text-based output file."""
    try:
        target_file = Path(file_path)
        parent_dir = target_file.parent
        suffix = target_file.suffix.lower()

        text_extensions = [".md", ".txt", ".json", ".html", ".tex", ".latex"]

        if suffix not in text_extensions:
            return {
                "status": "error",
                "error": f"Unsupported file format: {suffix}. Supported formats: {', '.join(text_extensions)}",
            }

        if not target_file.exists():
            if not parent_dir.exists():
                return {"status": "error", "error": f"Directory does not exist: {parent_dir}"}

            similar_files_paths = [
                str(f) for f in parent_dir.rglob(f"*{suffix}") if f.is_file()
            ]

            if similar_files_paths:
                if len(similar_files_paths) == 1:
                    alternative_file = similar_files_paths[0]
                    try:
                        with open(alternative_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        return {
                            "status": "success",
                            "content": content,
                            "message": f"File {target_file.name} was not found. Returned {Path(alternative_file).name} instead.",
                        }
                    except Exception as e:
                        return {
                            "status": "error",
                            "error": f"Failed to read fallback file: {str(e)}",
                        }
                else:
                    suggestion = f"Did you mean: {', '.join(similar_files_paths)}?"
                    return {
                        "status": "error",
                        "error": f"File {target_file.name} was not found. Similar files under {parent_dir}: {suggestion}",
                    }
            else:
                return {
                    "status": "error",
                    "error": f"File {target_file.name} was not found, and no other {suffix} files were found under {parent_dir}.",
                }

        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content}

    except Exception as e:
        config.logger.error(f"Error while reading file: {str(e)}")
        return {"status": "error", "error": str(e)}


async def find_and_read_markdown_content(result_path: str) -> Dict[str, Any]:
    """Search a result directory for readable Markdown or text outputs."""
    if not result_path:
        return {"status": "warning", "message": "No valid result path was provided"}

    base_path = Path(result_path)
    if not base_path.exists():
        return {"status": "warning", "message": f"Result path does not exist: {result_path}"}

    unique_files = set()

    common_files = [
        base_path / "full.md",
        base_path / "full.txt",
        base_path / "output.md",
        base_path / "result.md",
    ]
    for f in common_files:
        if f.exists():
            unique_files.add(str(f))

    for subdir in base_path.iterdir():
        if subdir.is_dir():
            subdir_files = [
                subdir / "full.md",
                subdir / "full.txt",
                subdir / "output.md",
                subdir / "result.md",
            ]
            for f in subdir_files:
                if f.exists():
                    unique_files.add(str(f))

    for md_file in base_path.glob("**/*.md"):
        unique_files.add(str(md_file))
    for txt_file in base_path.glob("**/*.txt"):
        unique_files.add(str(txt_file))

    possible_files = [Path(f) for f in unique_files]

    config.logger.debug(f"Found {len(possible_files)} candidate output file(s)")

    found_contents = []

    for file_path in possible_files:
        if file_path.exists():
            result = await read_converted_file(str(file_path))
            if result["status"] == "success":
                config.logger.debug(f"Read converted content from: {file_path}")
                found_contents.append(
                    {"file_path": str(file_path), "content": result["content"]}
                )

    if found_contents:
        config.logger.debug(f"Found {len(found_contents)} readable file(s) in the result directory")
        if len(found_contents) == 1:
            return {
                "status": "success",
                "content": found_contents[0]["content"],
                "file_path": found_contents[0]["file_path"],
            }
        return {"status": "success", "contents": found_contents}

    return {
        "status": "warning",
        "message": f"Could not find any readable Markdown output in: {result_path}",
    }


async def _process_conversion_result(
    result: Dict[str, Any], source: str, is_url: bool = False
) -> Dict[str, Any]:
    """Normalize the conversion result into a consistent response shape."""
    filename = source.split("/")[-1]
    if is_url and "?" in filename:
        filename = filename.split("?")[0]
    elif not is_url:
        filename = Path(source).name

    base_result = {
        "filename": filename,
        "source_url" if is_url else "source_path": source,
    }

    if result["status"] == "success":
        result_path = result.get("result_path")

        config.logger.debug(f"result_path type: {type(result_path)}")

        if result_path:
            if isinstance(result_path, dict) and "results" in result_path:
                config.logger.debug("Detected batched result format")

                for item in result_path.get("results", []):
                    if item.get("filename") == filename or (
                        not is_url and Path(source).name == item.get("filename")
                    ):
                        if item.get("status") == "success" and "content" in item:
                            base_result.update(
                                {
                                    "status": "success",
                                    "content": item.get("content", ""),
                                }
                            )
                            if "extract_path" in item:
                                base_result["extract_path"] = item["extract_path"]
                            return base_result
                        elif item.get("status") == "error":
                            base_result.update(
                                {
                                    "status": "error",
                                    "error_message": item.get(
                                        "error_message", "File processing failed"
                                    ),
                                }
                            )
                            return base_result

                if "extract_dir" in result_path:
                    config.logger.debug(f"Trying extract_dir fallback: {result_path['extract_dir']}")
                    try:
                        content_result = await find_and_read_markdown_content(
                            result_path["extract_dir"]
                        )
                        if content_result.get("status") == "success":
                            base_result.update(
                                {
                                    "status": "success",
                                    "content": content_result.get("content", ""),
                                    "extract_path": result_path["extract_dir"],
                                }
                            )
                            return base_result
                    except Exception as e:
                        config.logger.error(f"Failed to read from extract_dir: {str(e)}")

                base_result.update(
                    {
                        "status": "error",
                        "error_message": "Could not find matching content in batched results",
                    }
                )

            elif isinstance(result_path, str):
                config.logger.debug(f"Processing string result path: {result_path}")
                content_result = await find_and_read_markdown_content(result_path)
                if content_result.get("status") == "success":
                    base_result.update(
                        {
                            "status": "success",
                            "content": content_result.get("content", ""),
                            "extract_path": result_path,
                        }
                    )
                else:
                    base_result.update(
                        {
                            "status": "error",
                            "error_message": f"Could not read conversion output: {content_result.get('message', '')}",
                        }
                    )

            elif isinstance(result_path, dict):
                config.logger.debug(f"Processing generic dict result path: {result_path}")
                extract_path = (
                    result_path.get("extract_dir")
                    or result_path.get("path")
                    or result_path.get("dir")
                )
                if extract_path and isinstance(extract_path, str):
                    try:
                        content_result = await find_and_read_markdown_content(
                            extract_path
                        )
                        if content_result.get("status") == "success":
                            base_result.update(
                                {
                                    "status": "success",
                                    "content": content_result.get("content", ""),
                                    "extract_path": extract_path,
                                }
                            )
                            return base_result
                    except Exception as e:
                        config.logger.error(f"Failed to read from extracted path: {str(e)}")

                base_result.update(
                    {"status": "error", "error_message": "Conversion result format is not recognized"}
                )
            else:
                base_result.update(
                    {
                        "status": "error",
                        "error_message": f"Unrecognized result_path type: {type(result_path)}",
                    }
                )
        else:
            base_result.update(
                {"status": "error", "error_message": "Conversion succeeded but no result path was returned"}
            )
    else:
        base_result.update(
            {"status": "error", "error_message": result.get("error", "Unknown error")}
        )

    return base_result


@mcp.tool()
async def parse_documents(
    file_sources: Annotated[
        str,
        Field(
            description="""File path or URL. Supported formats:
            - Single path or URL: "/path/to/file.pdf" or "https://example.com/document.pdf"
            - Multiple paths or URLs (comma-separated)
            - Mixed local paths and URLs
            Supported file types include pdf, ppt, pptx, doc, docx, jpg, jpeg, and png."""
        ),
    ],
    enable_ocr: Annotated[bool, Field(description="Enable OCR. Default: False")] = False,
    language: Annotated[
        str, Field(description='Document language code. Default: "ch".')
    ] = "ch",
    page_ranges: Annotated[
        str | None,
        Field(
            description='Optional remote API page range string, for example "2,4-6" or "2--2".'
        ),
    ] = None,
) -> Dict[str, Any]:
    """Convert local files and URLs to Markdown using the configured backend."""
    sources = parse_list_input(file_sources)
    if not sources:
        return {"status": "error", "error": "No valid file path or URL was provided"}

    sources = list(dict.fromkeys(sources))

    config.logger.debug(f"Deduplicated sources: {sources}")

    original_count = len(parse_list_input(file_sources))
    unique_count = len(sources)
    if original_count > unique_count:
        config.logger.debug(
            f"Duplicate sources were removed automatically: {original_count} -> {unique_count}"
        )

    url_paths = []
    file_paths = []

    for source in sources:
        if source.lower().startswith(("http://", "https://")):
            url_paths.append(source)
        else:
            file_paths.append(source)

    results = []

    if config.USE_LOCAL_API:
        if not file_paths:
            return {
                "status": "warning",
                "message": "Local API mode cannot process URLs, and no valid local file paths were provided",
            }

        config.logger.info(f"Processing {len(file_paths)} file(s) with the local API")

        for path in file_paths:
            try:
                if not Path(path).exists():
                    results.append(
                        {
                            "filename": Path(path).name,
                            "source_path": path,
                            "status": "error",
                            "error_message": f"File does not exist: {path}",
                        }
                    )
                    continue

                result = await local_parse_file(
                    file_path=path,
                    parse_method=("ocr" if enable_ocr else "txt"),
                )

                result_with_filename = {
                    "filename": Path(path).name,
                    "source_path": path,
                    **result,
                }
                results.append(result_with_filename)

            except Exception as e:
                config.logger.error(f"Error while processing file {path}: {str(e)}")
                results.append(
                    {
                        "filename": Path(path).name,
                        "source_path": path,
                        "status": "error",
                        "error_message": f"File processing raised an exception: {str(e)}",
                    }
                )

    else:
        if url_paths:
            config.logger.info(f"Processing {len(url_paths)} URL(s) with the remote API")

            try:
                url_result = await convert_file_url(
                    url=",".join(url_paths),
                    enable_ocr=enable_ocr,
                    language=language,
                    page_ranges=page_ranges,
                )

                if url_result["status"] == "success":
                    for url in url_paths:
                        result_item = await _process_conversion_result(
                            url_result, url, is_url=True
                        )
                        results.append(result_item)
                else:
                    for url in url_paths:
                        results.append(
                            {
                                "filename": url.split("/")[-1].split("?")[0],
                                "source_url": url,
                                "status": "error",
                                "error_message": url_result.get("error", "URL processing failed"),
                            }
                        )

            except Exception as e:
                config.logger.error(f"Error while processing URL(s): {str(e)}")
                for url in url_paths:
                    results.append(
                        {
                            "filename": url.split("/")[-1].split("?")[0],
                            "source_url": url,
                            "status": "error",
                            "error_message": f"URL processing raised an exception: {str(e)}",
                        }
                    )

        if file_paths:
            config.logger.info(f"Processing {len(file_paths)} local file(s) with the remote API")

            existing_files = []
            for file_path in file_paths:
                if not Path(file_path).exists():
                    results.append(
                        {
                            "filename": Path(file_path).name,
                            "source_path": file_path,
                            "status": "error",
                            "error_message": f"File does not exist: {file_path}",
                        }
                    )
                else:
                    existing_files.append(file_path)

            if existing_files:
                try:
                    file_result = await convert_file_path(
                        file_path=",".join(existing_files),
                        enable_ocr=enable_ocr,
                        language=language,
                        page_ranges=page_ranges,
                    )

                    config.logger.debug(f"file_result: {file_result}")

                    if file_result["status"] == "success":
                        for file_path in existing_files:
                            result_item = await _process_conversion_result(
                                file_result, file_path, is_url=False
                            )
                            results.append(result_item)
                    else:
                        for file_path in existing_files:
                            results.append(
                                {
                                    "filename": Path(file_path).name,
                                    "source_path": file_path,
                                    "status": "error",
                                    "error_message": file_result.get(
                                        "error", "File processing failed"
                                    ),
                                }
                            )

                except Exception as e:
                    config.logger.error(f"Error while processing local file(s): {str(e)}")
                    for file_path in existing_files:
                        results.append(
                            {
                                "filename": Path(file_path).name,
                                "source_path": file_path,
                                "status": "error",
                                "error_message": f"File processing raised an exception: {str(e)}",
                            }
                        )

    if not results:
        return {"status": "error", "error": "No files were processed"}

    success_count = len([r for r in results if r.get("status") == "success"])
    error_count = len([r for r in results if r.get("status") == "error"])
    total_count = len(results)

    if len(results) == 1:
        result = results[0].copy()
        if "filename" in result:
            del result["filename"]
        if "source_path" in result:
            del result["source_path"]
        if "source_url" in result:
            del result["source_url"]
        return result

    overall_status = "success"
    if success_count == 0:
        overall_status = "error"
    elif error_count > 0:
        overall_status = "partial_success"

    return {
        "status": overall_status,
        "results": results,
        "summary": {
            "total_files": total_count,
            "success_count": success_count,
            "error_count": error_count,
        },
    }


@mcp.tool()
async def get_ocr_languages() -> Dict[str, Any]:
    """Return the OCR languages supported by MinerU."""
    try:
        languages = get_language_list()
        return {"status": "success", "languages": languages}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _parse_file_local(
    file_path: str,
    parse_method: str = "auto",
) -> Dict[str, Any]:
    """Send a file to the locally configured MinerU API."""
    api_url = f"{config.LOCAL_MINERU_API_BASE}/file_parse"

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    with open(file_path_obj, "rb") as f:
        file_data = f.read()

    file_type = file_path_obj.suffix.lower()
    form_data = aiohttp.FormData()
    form_data.add_field(
        "file", file_data, filename=file_path_obj.name, content_type=file_type
    )
    form_data.add_field("parse_method", parse_method)

    config.logger.debug(f"Sending local API request to: {api_url}")
    config.logger.debug(f"Uploading file: {file_path_obj.name} (size: {len(file_data)} bytes)")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=form_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    config.logger.error(
                        f"Local API returned status {response.status}: {error_text}"
                    )
                    raise RuntimeError(f"Local API error: {response.status}, {error_text}")

                result = await response.json()

                config.logger.debug(f"Local API response: {result}")

                if "error" in result:
                    return {"status": "error", "error": result["error"]}

                return {"status": "success", "result": result}
    except aiohttp.ClientError as e:
        error_msg = f"Error while communicating with the local API: {str(e)}"
        config.logger.error(error_msg)
        raise RuntimeError(error_msg)
