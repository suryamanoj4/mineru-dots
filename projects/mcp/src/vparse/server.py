"""FastMCP server implementation for VParse File to Markdown conversion."""

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
from .api import VParseClient
from .language import get_language_list

# Initialize FastMCP server
mcp = FastMCP(
    name="VParse File to Markdown Conversion",
    instructions="""
    A document conversion tool that transforms documents into formats like Markdown and JSON.
    Supports various file formats including PDF, Word, PPT, and images (JPG, PNG, JPEG).

    System Tools:
    parse_documents: Parse documents (supports local files and URLs with auto-content extraction).
    get_ocr_languages: Retrieve the list of supported OCR languages.
    """,
)

# Global client instance
_client_instance: Optional[VParseClient] = None


def create_starlette_app(mcp_server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application for SSE transport.

    Args:
        mcp_server: MCP server instance
        debug: Whether to enable debug mode.

    Returns:
        Starlette: Configured Starlette application instance
    """
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle SSE connection requests."""
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
    """Run the FastMCP server.

    Args:
        mode: Running mode (stdio, sse, streamable-http).
        port: Server port, defaults to 8001 (effective only in HTTP mode).
        host: Server host address, defaults to 127.0.0.1 (effective only in HTTP mode).
    """
    # Ensure output directory exists
    config.ensure_output_dir(output_dir)

    # Check if API key is set
    if not config.VPARSE_API_KEY:
        config.logger.warning("Warning: VPARSE_API_KEY environment variable is not set.")
        config.logger.warning("Use the following command to set it: export VPARSE_API_KEY=your_api_key")

    # Get MCP server instance
    mcp_server = mcp._mcp_server

    try:
        # Run the server
        if mode == "sse":
            config.logger.info(f"Starting SSE server: {host}:{port}")
            starlette_app = create_starlette_app(mcp_server, debug=True)
            uvicorn.run(starlette_app, host=host, port=port)
        elif mode == "streamable-http":
            config.logger.info(f"Starting Streamable HTTP server: {host}:{port}")
            # Pass port parameter in HTTP mode
            mcp.run(mode, port=port)
        else:
            # Default to stdio mode
            config.logger.info("Starting STDIO server")
            mcp.run(mode or "stdio")
    except Exception as e:
        config.logger.error(f"\n❌ Service exited with exception: {str(e)}")
        traceback.print_exc()
    finally:
        # Clean up resources
        cleanup_resources()


def cleanup_resources():
    """Clean up global resources."""
    global _client_instance
    if _client_instance is not None:
        try:
            # Call close method if client has it
            if hasattr(_client_instance, "close"):
                _client_instance.close()
        except Exception as e:
            config.logger.error(f"Error cleaning up client resources: {str(e)}")
        finally:
            _client_instance = None
    config.logger.info("Resource cleanup complete")


def get_client() -> VParseClient:
    """Get a singleton instance of VParseClient. Initialize if not already initialized."""
    global _client_instance
    if _client_instance is None:
        _client_instance = VParseClient()  # Initialization happens here
    return _client_instance


# Markdown files output directory
output_dir = config.DEFAULT_OUTPUT_DIR


def set_output_dir(dir_path: str):
    """Set the output directory for converted files."""
    global output_dir
    output_dir = dir_path
    config.ensure_output_dir(output_dir)
    return output_dir


def parse_list_input(input_str: str) -> List[str]:
    """
    Parse a string input potentially containing multiple items separated by commas or newlines.

    Args:
        input_str: String potentially containing multiple items

    Returns:
        List of parsed items
    """
    if not input_str:
        return []

    # Split by comma, newline, or space
    items = re.split(r"[,\n\s]+", input_str)

    # Remove empty items and handle quoted items
    result = []
    for item in items:
        item = item.strip()
        # Remove quotes if present
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
    """
    Convert files from URLs to Markdown format. Supports single or multiple URL processing.

    Returns:
        Success: {"status": "success", "result_path": "output_directory_path"}
        Failure: {"status": "error", "error": "error_message"}
    """
    urls_to_process = None

    # Check for URL configuration in dict or list of dicts format.
    if isinstance(url, dict):
        # Single URL configuration dictionary
        urls_to_process = url
    elif isinstance(url, list) and len(url) > 0 and isinstance(url[0], dict):
        # List of URL configuration dictionaries
        urls_to_process = url
    elif isinstance(url, str):
        # Check for multi-URL configuration in JSON string format.
        if url.strip().startswith("[") and url.strip().endswith("]"):
            try:
                # Attempt to parse JSON string as a list of URL configurations
                url_configs = json.loads(url)
                if not isinstance(url_configs, list):
                    raise ValueError("JSON URL configuration must be in list format")

                urls_to_process = url_configs
            except json.JSONDecodeError:
                # Not valid JSON, continue with string parsing
                pass

    if urls_to_process is None:
        # Parse normal URL list
        urls = parse_list_input(url)

        if not urls:
            raise ValueError("No valid URLs provided")

        if len(urls) == 1:
            # Single URL processing
            urls_to_process = {"url": urls[0], "is_ocr": enable_ocr}
        else:
            # Multiple URLs, convert to list of URL configurations
            urls_to_process = []
            for url_item in urls:
                urls_to_process.append(
                    {
                        "url": url_item,
                        "is_ocr": enable_ocr,
                    }
                )

    # Use submit_file_url_task to process URLs
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
    """
    Convert local files to Markdown format. Supports single or multiple file batch processing.

    Returns:
        Success: {"status": "success", "result_path": "output_directory_path"}
        Failure: {"status": "error", "error": "error_message"}
    """

    files_to_process = None

    # Check for file configuration in dict or list of dicts format.
    if isinstance(file_path, dict):
        # Single file configuration dictionary
        files_to_process = file_path
    elif (
        isinstance(file_path, list)
        and len(file_path) > 0
        and isinstance(file_path[0], dict)
    ):
        # List of file configuration dictionaries
        files_to_process = file_path
    elif isinstance(file_path, str):
        # Check for multi-file configuration in JSON string format.
        if file_path.strip().startswith("[") and file_path.strip().endswith("]"):
            try:
                # Attempt to parse JSON string as a list of file configurations
                file_configs = json.loads(file_path)
                if not isinstance(file_configs, list):
                    raise ValueError("JSON file configuration must be in list format")

                files_to_process = file_configs
            except json.JSONDecodeError:
                # Not valid JSON, continue with string parsing
                pass

    if files_to_process is None:
        # Parse normal file path list
        file_paths = parse_list_input(file_path)

        if not file_paths:
            raise ValueError("No valid file paths provided")

        if len(file_paths) == 1:
            # Single file processing
            files_to_process = {
                "path": file_paths[0],
                "is_ocr": enable_ocr,
            }
        else:
            # Multiple file paths, convert to list of file configurations
            files_to_process = []
            for i, path in enumerate(file_paths):
                files_to_process.append(
                    {
                        "path": path,
                        "is_ocr": enable_ocr,
                    }
                )

    # Use submit_file_task to process files
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
    """
    Parse a file using local or remote API based on environment variable settings.

    Returns:
        Success: {"status": "success", "result": result} or {"status": "success", "result_path": "output_directory_path"}
        Failure: {"status": "error", "error": "error_message"}
    """
    file_path = Path(file_path)

    # Check if file exists
    if not file_path.exists():
        return {"status": "error", "error": f"File does not exist: {file_path}"}

    try:
        # Determine whether to use local or remote API based on environment variables
        if config.USE_LOCAL_API:
            config.logger.debug(f"Using local API: {config.LOCAL_VPARSE_API_BASE}")
            return await _parse_file_local(
                file_path=str(file_path),
                parse_method=parse_method,
            )
        else:
            return {"status": "error", "error": "Remote API not configured"}
    except Exception as e:
        config.logger.error(f"Error parsing file: {str(e)}")
        return {"status": "error", "error": str(e)}


async def read_converted_file(
    file_path: str,
) -> Dict[str, Any]:
    """
    Read the content of a converted file. Primarily supports Markdown and other text formats.

    Returns:
        Success: {"status": "success", "content": "file_content"}
        Failure: {"status": "error", "error": "error_message"}
    """
    try:
        target_file = Path(file_path)
        parent_dir = target_file.parent
        suffix = target_file.suffix.lower()

        # Supported text file formats
        text_extensions = [".md", ".txt", ".json", ".html", ".tex", ".latex"]

        if suffix not in text_extensions:
            return {
                "status": "error",
                "error": f"Unsupported file format: {suffix}. Currently supported: {', '.join(text_extensions)}",
            }

        if not target_file.exists():
            if not parent_dir.exists():
                return {"status": "error", "error": f"Directory {parent_dir} does not exist"}

            # Recursively search for files with the same suffix in all subdirectories
            similar_files_paths = [
                str(f) for f in parent_dir.rglob(f"*{suffix}") if f.is_file()
            ]

            if similar_files_paths:
                if len(similar_files_paths) == 1:
                    # If only one file is found, read and return its content
                    alternative_file = similar_files_paths[0]
                    try:
                        with open(alternative_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        return {
                            "status": "success",
                            "content": content,
                            "message": f"File {target_file.name} not found, but {Path(alternative_file).name} was found; content returned.",
                        }
                    except Exception as e:
                        return {
                            "status": "error",
                            "error": f"Error attempting to read alternative file: {str(e)}",
                        }
                else:
                    # If multiple files are found, provide a list of suggestions
                    suggestion = f"Were you looking for: {', '.join(similar_files_paths)}?"
                    return {
                        "status": "error",
                        "error": f"File {target_file.name} does not exist. Found the following similar files in {parent_dir} and its subdirectories: {suggestion}",
                    }
            else:
                return {
                    "status": "error",
                    "error": f"File {target_file.name} does not exist, and no other {suffix} files were found in {parent_dir} or its subdirectories.",
                }

        # Read in text mode
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": content}

    except Exception as e:
        config.logger.error(f"Error reading file: {str(e)}")
        return {"status": "error", "error": str(e)}


async def find_and_read_markdown_content(result_path: str) -> Dict[str, Any]:
    """
    Search for and read Markdown file content in the given path.
    Looks in all possible locations and returns all valid content found.

    Args:
        result_path: Path to the result directory

    Returns:
        Dict[str, Any]: Dictionary containing all file content or error messages
    """
    if not result_path:
        return {"status": "warning", "message": "No valid result path provided"}

    base_path = Path(result_path)
    if not base_path.exists():
        return {"status": "warning", "message": f"Result path does not exist: {result_path}"}

    # Use a set to store file paths to ensure uniqueness
    unique_files = set()

    # Add common filenames
    common_files = [
        base_path / "full.md",
        base_path / "full.txt",
        base_path / "output.md",
        base_path / "result.md",
    ]
    for f in common_files:
        if f.exists():
            unique_files.add(str(f))

    # Add common filenames in subdirectories
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

    # Find all .md and .txt files
    for md_file in base_path.glob("**/*.md"):
        unique_files.add(str(md_file))
    for txt_file in base_path.glob("**/*.txt"):
        unique_files.add(str(txt_file))

    # Convert set back to list of Path objects
    possible_files = [Path(f) for f in unique_files]

    config.logger.debug(f"Found {len(possible_files)} possible files")

    # Collect all valid file contents found
    found_contents = []

    # Attempt to read each possible file
    for file_path in possible_files:
        if file_path.exists():
            result = await read_converted_file(str(file_path))
            if result["status"] == "success":
                config.logger.debug(f"Successfully read file content: {file_path}")
                found_contents.append(
                    {"file_path": str(file_path), "content": result["content"]}
                )

    # If file content was found
    if found_contents:
        config.logger.debug(f"Found {len(found_contents)} readable files in result directory")
        # If only one file is found, maintain backward compatible return format
        if len(found_contents) == 1:
            return {
                "status": "success",
                "content": found_contents[0]["content"],
                "file_path": found_contents[0]["file_path"],
            }
        # If multiple files are found, return list of contents
        else:
            return {"status": "success", "contents": found_contents}

    # If no valid files were found
    return {
        "status": "warning",
        "message": f"Could not find any readable Markdown files in result directory: {result_path}",
    }


async def _process_conversion_result(
    result: Dict[str, Any], source: str, is_url: bool = False
) -> Dict[str, Any]:
    """
    Process conversion results and unify output formatting.

    Args:
        result: Result returned by the conversion function
        source: Source file path or URL
        is_url: Whether it is a URL

    Returns:
        Formatted result dictionary
    """
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
        # Get result_path, which could be a string or a dictionary
        result_path = result.get("result_path")

        # Log debug info
        config.logger.debug(f"Processing result result_path type: {type(result_path)}")

        if result_path:
            # Case 1: result_path is a dictionary containing a 'results' field (batch processing results)
            if isinstance(result_path, dict) and "results" in result_path:
                config.logger.debug("Detected batch processing result format")

                # Find result matching current source file
                for item in result_path.get("results", []):
                    if item.get("filename") == filename or (
                        not is_url and Path(source).name == item.get("filename")
                    ):
                        # Return matching item status directly, whether success or error
                        if item.get("status") == "success" and "content" in item:
                            base_result.update(
                                {
                                    "status": "success",
                                    "content": item.get("content", ""),
                                }
                            )
                            # Add extract_path if present
                            if "extract_path" in item:
                                base_result["extract_path"] = item["extract_path"]
                            return base_result
                        elif item.get("status") == "error":
                            # Handle failed file, return error status directly
                            base_result.update(
                                {
                                    "status": "error",
                                    "error_message": item.get(
                                        "error_message", "File processing failed"
                                    ),
                                }
                            )
                            return base_result

                # If no matching result but extract_dir exists, try reading from there
                if "extract_dir" in result_path:
                    config.logger.debug(
                        f"Attempting to read from extract_dir: {result_path['extract_dir']}"
                    )
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
                        config.logger.error(f"Error reading content from extract_dir: {str(e)}")

                # If all above methods fail, return error
                base_result.update(
                    {
                        "status": "error",
                        "error_message": "Could not find matching content in batch results",
                    }
                )

            # Case 2: result_path is a string (traditional format)
            elif isinstance(result_path, str):
                config.logger.debug(f"Processing traditional format result path: {result_path}")
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
                            "error_message": f"Could not read conversion result: {content_result.get('message', '')}",
                        }
                    )

            # Case 3: result_path is another type of dictionary (attempt to process)
            elif isinstance(result_path, dict):
                config.logger.debug(f"Processing other dictionary format: {result_path}")
                # Attempt to extract possible path from dictionary
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
                        config.logger.error(f"Error reading from extract_path: {str(e)}")

                # If no valid path found, return error
                base_result.update(
                    {"status": "error", "error_message": "Conversion result format not recognized"}
                )
            else:
                # Case 4: result_path is of unknown type (error)
                base_result.update(
                    {
                        "status": "error",
                        "error_message": f"Unrecognized result_path type: {type(result_path)}",
                    }
                )
        else:
            base_result.update(
                {"status": "error", "error_message": "Conversion succeeded but no result path returned"}
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
            description="""File paths or URLs, supporting the following formats:
            - Single path or URL: "/path/to/file.pdf" or "https://example.com/document.pdf"
            - Multiple paths or URLs (comma-separated): "/path/to/file1.pdf, /path/to/file2.pdf" or
              "https://example.com/doc1.pdf, https://example.com/doc2.pdf"
            - Mixed paths and URLs: "/path/to/file.pdf, https://example.com/document.pdf"
            (Supports PDF, PPT, PPTX, DOC, DOCX, and image formats like JPG, JPEG, PNG)"""
        ),
    ],
    # General parameters
    enable_ocr: Annotated[bool, Field(description="Enable OCR recognition, defaults to False")] = False,
    language: Annotated[
        str, Field(description='Document language, defaults to "ch" (Chinese), optionally "en" (English), etc.')
    ] = "ch",
    # Remote API parameters
    page_ranges: Annotated[
        str | None,
        Field(
            description='Specify page ranges as a comma-separated string. For example: "2,4-6" selects page 2 and pages 4 to 6; "2--2" selects from page 2 to the second to last page. (Remote API), defaults to None'
        ),
    ] = None,
) -> Dict[str, Any]:
    """
    Unified interface to convert files to Markdown. Supports local files and URLs, automatically choosing the appropriate processing method based on USE_LOCAL_API configuration.

    When USE_LOCAL_API=true:
    - Filters out URL paths starting with http/https
    - Uses local API for local files

    When USE_LOCAL_API=false:
    - Uses convert_file_url for paths starting with http/https
    - Uses convert_file_path for other paths

    After processing, it automatically attempts to read and return the converted file content.

    Returns:
        Success: {"status": "success", "content": "file_content"} or {"status": "success", "results": [list_of_results]}
        Failure: {"status": "error", "error": "error_message"}
    """
    # Parse path list
    sources = parse_list_input(file_sources)
    if not sources:
        return {"status": "error", "error": "No valid file paths or URLs provided"}

    # Deduplicate while preserving order using a dictionary
    sources = list(dict.fromkeys(sources))

    config.logger.debug(f"Deduplicated file paths: {sources}")

    # Record deduplication info
    original_count = len(parse_list_input(file_sources))
    unique_count = len(sources)
    if original_count > unique_count:
        config.logger.debug(
            f"Detected duplicate paths, auto-deduplicated: {original_count} -> {unique_count}"
        )

    # Categorize paths
    url_paths = []
    file_paths = []

    for source in sources:
        if source.lower().startswith(("http://", "https://")):
            url_paths.append(source)
        else:
            file_paths.append(source)

    results = []

    # Determine processing method based on USE_LOCAL_API
    if config.USE_LOCAL_API:
        # In local API mode, only process local file paths
        if not file_paths:
            return {
                "status": "warning",
                "message": "In local API mode, URLs cannot be processed and no valid local file paths were provided",
            }

        config.logger.info(f"Processing {len(file_paths)} files using local API")

        # Process local files one by one
        for path in file_paths:
            try:
                # Skip non-existent files
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
                    parse_method=(
                        "ocr" if enable_ocr else "txt"
                    ),  # Use ocr if enabled, otherwise txt
                )

                # Add filename info
                result_with_filename = {
                    "filename": Path(path).name,
                    "source_path": path,
                    **result,
                }
                results.append(result_with_filename)

            except Exception as e:
                # Exception during file processing, log error but continue with next file
                config.logger.error(f"Error processing file {path}: {str(e)}")
                results.append(
                    {
                        "filename": Path(path).name,
                        "source_path": path,
                        "status": "error",
                        "error_message": f"Exception during file processing: {str(e)}",
                    }
                )

    else:
        # In remote API mode, process URLs and local file paths separately
        if url_paths:
            config.logger.info(f"Processing {len(url_paths)} file URLs using remote API")

            try:
                # Call convert_file_url to process URLs
                url_result = await convert_file_url(
                    url=",".join(url_paths),
                    enable_ocr=enable_ocr,
                    language=language,
                    page_ranges=page_ranges,
                )

                if url_result["status"] == "success":
                    # Generate results for each URL
                    for url in url_paths:
                        result_item = await _process_conversion_result(
                            url_result, url, is_url=True
                        )
                        results.append(result_item)
                else:
                    # Conversion failed, add error results for all URLs
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
                config.logger.error(f"Error processing URL: {str(e)}")
                for url in url_paths:
                    results.append(
                        {
                            "filename": url.split("/")[-1].split("?")[0],
                            "source_url": url,
                            "status": "error",
                            "error_message": f"Exception during URL processing: {str(e)}",
                        }
                    )

        if file_paths:
            config.logger.info(f"Processing {len(file_paths)} local files using remote API")

            # Filter for existent files
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
                    # Call convert_file_path to process local files
                    file_result = await convert_file_path(
                        file_path=",".join(existing_files),
                        enable_ocr=enable_ocr,
                        language=language,
                        page_ranges=page_ranges,
                    )

                    config.logger.debug(f"file_result: {file_result}")

                    if file_result["status"] == "success":
                        # Generate results for each file
                        for file_path in existing_files:
                            result_item = await _process_conversion_result(
                                file_result, file_path, is_url=False
                            )
                            results.append(result_item)
                    else:
                        # Conversion failed, add error results for all files
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
                    config.logger.error(f"Error processing local file: {str(e)}")
                    for file_path in existing_files:
                        results.append(
                            {
                                "filename": Path(file_path).name,
                                "source_path": file_path,
                                "status": "error",
                                "error_message": f"Exception during file processing: {str(e)}",
                            }
                        )

    # Handle case where results are empty
    if not results:
        return {"status": "error", "error": "No files processed"}

    # Calculate success and failure statistics
    success_count = len([r for r in results if r.get("status") == "success"])
    error_count = len([r for r in results if r.get("status") == "error"])
    total_count = len(results)

    # If only one result, return it directly for backward compatibility
    if len(results) == 1:
        result = results[0].copy()
        # Remove newly added fields for backward compatibility
        if "filename" in result:
            del result["filename"]
        if "source_path" in result:
            del result["source_path"]
        if "source_url" in result:
            del result["source_url"]
        return result

    # For multiple results, return a detailed list
    # Determine overall status based on success/error cases
    overall_status = "success"
    if success_count == 0:
        # All files failed
        overall_status = "error"
    elif error_count > 0:
        # Partial failure
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
    """
    Retrieve the list of supported OCR languages.

    Returns:
        Dict[str, Any]: Dictionary containing the list of all supported OCR languages
    """
    try:
        # Get language list from language module
        languages = get_language_list()
        return {"status": "success", "languages": languages}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _parse_file_local(
    file_path: str,
    parse_method: str = "auto",
) -> Dict[str, Any]:
    """
    Parse a file using the local API.

    Args:
        file_path: Path to the file to be parsed
        parse_method: Parsing method

    Returns:
        Dict[str, Any]: Dictionary containing the parsing result
    """
    # API URL path
    api_url = f"{config.LOCAL_VPARSE_API_BASE}/file_parse"

    # Use Path object to ensure correct file path
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    # Read binary file data
    with open(file_path_obj, "rb") as f:
        file_data = f.read()

    # Prepare form data for file upload
    file_type = file_path_obj.suffix.lower()
    form_data = aiohttp.FormData()
    form_data.add_field(
        "file", file_data, filename=file_path_obj.name, content_type=file_type
    )
    form_data.add_field("parse_method", parse_method)

    config.logger.debug(f"Sending local API request to: {api_url}")
    config.logger.debug(f"Uploading file: {file_path_obj.name} (Size: {len(file_data)} bytes)")

    # Send request
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=form_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    config.logger.error(
                        f"API returned error status code: {response.status}, error info: {error_text}"
                    )
                    raise RuntimeError(f"API returned error: {response.status}, {error_text}")

                result = await response.json()

                config.logger.debug(f"Local API response: {result}")

                # Handle response
                if "error" in result:
                    return {"status": "error", "error": result["error"]}

                return {"status": "success", "result": result}
    except aiohttp.ClientError as e:
        error_msg = f"Error communicating with local API: {str(e)}"
        config.logger.error(error_msg)
        raise RuntimeError(error_msg)
