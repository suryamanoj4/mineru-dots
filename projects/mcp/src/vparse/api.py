"""VParse File转Markdown转换的API客户端。"""

import asyncio
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiohttp
import requests

from . import config


def singleton_func(cls):
    instance = {}

    def _singleton(*args, **kwargs):
        if cls not in instance:
            instance[cls] = cls(*args, **kwargs)
        return instance[cls]

    return _singleton


@singleton_func
class VParseClient:
    """
    用于与 VParse API 交互以将 File 转换为 Markdown 的客户端。
    """

    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None):
        """
        初始化 VParse API 客户端。

        Args:
            api_base: VParse API 的基础 URL (默认: 从环境变量获取)
            api_key: 用于向 VParse 进行身份验证的 API 密钥 (默认: 从环境变量获取)
        """
        self.api_base = api_base or config.VPARSE_API_BASE
        self.api_key = api_key or config.VPARSE_API_KEY

        if not self.api_key:
            # Provide a user-friendly error message
            raise ValueError(
                "错误: VParse API 密钥 (VPARSE_API_KEY) 未设置或为空。\n"
                "请确保已设置 VPARSE_API_KEY 环境变量，例如:\n"
                "  export VPARSE_API_KEY='your_actual_api_key'\n"
                "或者，在项目根目录的 `.env` 文件中定义该变量。"
            )

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        向 VParse API 发出请求。

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (excluding base URL)
            **kwargs: Other parameters passed to the aiohttp request

        Returns:
            dict: API response (JSON format)
        """
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        if "headers" in kwargs:
            kwargs["headers"].update(headers)
        else:
            kwargs["headers"] = headers

        # Create a copy of parameters without auth info for logging
        log_kwargs = kwargs.copy()
        if "headers" in log_kwargs and "Authorization" in log_kwargs["headers"]:
            log_kwargs["headers"] = log_kwargs["headers"].copy()
            log_kwargs["headers"]["Authorization"] = "Bearer ****"  # Hide API key

        config.logger.debug(f"API Request: {method} {url}")
        config.logger.debug(f"Request Parameters: {log_kwargs}")

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                response_json = await response.json()

                config.logger.debug(f"API Response: {response_json}")

                return response_json

    async def submit_file_url_task(
        self,
        urls: Union[str, List[Union[str, Dict[str, Any]]], Dict[str, Any]],
        enable_ocr: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit file URL for Markdown conversion. Supports single or batch URL processing.

        Args:
            urls: Can be one of:
                1. Single URL string
                2. List of URL strings
                3. List of dicts containing URL configs:
                   - url: File URL (required)
                   - is_ocr: Enable OCR (optional)
                   - data_id: File ID (optional)
                   - page_ranges: Page range (optional)
            enable_ocr: Whether to enable OCR for conversion (default for all files)
            language: Specify document language, default "ch"
            page_ranges: Specify page ranges as a comma-separated string. For example: "2,4-6" selects page 2 and pages 4 to 6; "2--2" selects from page 2 to the second to last page.

        Returns:
            dict: Task info including batch_id
        """
        # Count number of URLs
        url_count = 1
        if isinstance(urls, list):
            url_count = len(urls)
        config.logger.debug(
            f"Calling submit_file_url_task: {url_count} URLs, "
            + f"ocr={enable_ocr}, "
            + f"language={language}"
        )

        # Process input, ensure we have a list of URL configurations
        urls_config = []

        # Convert input to standard format
        if isinstance(urls, str):
            urls_config.append(
                {"url": urls, "is_ocr": enable_ocr, "page_ranges": page_ranges}
            )

        elif isinstance(urls, list):
            # Process list of URLs or URL configurations
            for i, url_item in enumerate(urls):
                if isinstance(url_item, str):
                    # Simple URL string
                    urls_config.append(
                        {
                            "url": url_item,
                            "is_ocr": enable_ocr,
                            "page_ranges": page_ranges,
                        }
                    )

                elif isinstance(url_item, dict):
                    # URL dictionary with detailed configuration
                    if "url" not in url_item:
                        raise ValueError(f"URL config must include 'url' field: {url_item}")

                    url_is_ocr = url_item.get("is_ocr", enable_ocr)
                    url_page_ranges = url_item.get("page_ranges", page_ranges)

                    url_config = {"url": url_item["url"], "is_ocr": url_is_ocr}
                    if url_page_ranges is not None:
                        url_config["page_ranges"] = url_page_ranges

                    urls_config.append(url_config)
                else:
                    raise TypeError(f"Unsupported URL config type: {type(url_item)}")
        elif isinstance(urls, dict):
            # Single URL configuration dictionary
            if "url" not in urls:
                raise ValueError(f"URL config must include 'url' field: {urls}")

            url_is_ocr = urls.get("is_ocr", enable_ocr)
            url_page_ranges = urls.get("page_ranges", page_ranges)

            url_config = {"url": urls["url"], "is_ocr": url_is_ocr}
            if url_page_ranges is not None:
                url_config["page_ranges"] = url_page_ranges

            urls_config.append(url_config)
        else:
            raise TypeError(f"urls must be string, list, or dict, not {type(urls)}")

        # Construct API request payload
        files_payload = urls_config  # Direct use of URL config

        payload = {
            "language": language,
            "files": files_payload,
        }

        # Call batch API
        response = await self._request(
            "POST", "/api/v4/extract/task/batch", json=payload
        )

        # Check response
        if "data" not in response or "batch_id" not in response["data"]:
            raise ValueError(f"Failed to submit batch URL task: {response}")

        batch_id = response["data"]["batch_id"]

        config.logger.info(f"Processing {len(urls_config)} file URLs")
        config.logger.debug(f"Batch URL task submitted, batch ID: {batch_id}")

        # Return response with batch_id and URL information
        result = {
            "data": {
                "batch_id": batch_id,
                "uploaded_files": [url_config.get("url") for url_config in urls_config],
            }
        }

        # For single URL case, set file_name for backward compatibility
        if len(urls_config) == 1:
            url = urls_config[0]["url"]
            # Extract filename from URL
            file_name = url.split("/")[-1]
            result["data"]["file_name"] = file_name

        return result

    async def submit_file_task(
        self,
        files: Union[str, List[Union[str, Dict[str, Any]]], Dict[str, Any]],
        enable_ocr: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit local file to convert to Markdown. Supports single file path or batch configuration.

        Args:
            files: One of:
                1. Single file path string
                2. List of file paths
                3. List of dicts containing file configs:
                   - path/name: File path or name
                   - is_ocr: Enable OCR (optional)
                   - data_id: File data ID (optional)
                   - page_ranges: Page range (optional)
            enable_ocr: Whether to enable OCR for conversion (default for all files)
            language: Specify document language, default "ch"
            page_ranges: Specify page ranges as a comma-separated string. For example: "2,4-6" selects page 2 and pages 4 to 6; "2--2" selects from page 2 to the second to last page.

        Returns:
            dict: Task info including batch_id
        """
        # Count files
        file_count = 1
        if isinstance(files, list):
            file_count = len(files)
        config.logger.debug(
            f"Calling submit_file_task: {file_count} files, "
            + f"ocr={enable_ocr}, "
            + f"language={language}"
        )

        # Process input, ensure we have a list of file configurations
        files_config = []

        # Convert input to standard format
        if isinstance(files, str):
            # Single file path
            file_path = Path(files)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            files_config.append(
                {
                    "path": file_path,
                    "name": file_path.name,
                    "is_ocr": enable_ocr,
                    "page_ranges": page_ranges,
                }
            )

        elif isinstance(files, list):
            # Process list of file paths or file configurations
            for i, file_item in enumerate(files):
                if isinstance(file_item, str):
                    # Simple file path
                    file_path = Path(file_item)
                    if not file_path.exists():
                        raise FileNotFoundError(f"File not found: {file_path}")

                    files_config.append(
                        {
                            "path": file_path,
                            "name": file_path.name,
                            "is_ocr": enable_ocr,
                            "page_ranges": page_ranges,
                        }
                    )

                elif isinstance(file_item, dict):
                    # File dictionary with detailed configuration
                    if "path" not in file_item and "name" not in file_item:
                        raise ValueError(
                            f"File config must include 'path' or 'name' field: {file_item}"
                        )

                    if "path" in file_item:
                        file_path = Path(file_item["path"])
                        if not file_path.exists():
                            raise FileNotFoundError(f"File not found: {file_path}")

                        file_name = file_path.name
                    else:
                        file_name = file_item["name"]
                        file_path = None

                    file_is_ocr = file_item.get("is_ocr", enable_ocr)
                    file_page_ranges = file_item.get("page_ranges", page_ranges)

                    file_config = {
                        "path": file_path,
                        "name": file_name,
                        "is_ocr": file_is_ocr,
                    }
                    if file_page_ranges is not None:
                        file_config["page_ranges"] = file_page_ranges

                    files_config.append(file_config)
                else:
                    raise TypeError(f"Unsupported file config type: {type(file_item)}")
        elif isinstance(files, dict):
            # Single file configuration dictionary
            if "path" not in files and "name" not in files:
                raise ValueError(f"File config must include 'path' or 'name' field: {files}")

            if "path" in files:
                file_path = Path(files["path"])
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                file_name = file_path.name
            else:
                file_name = files["name"]
                file_path = None

            file_is_ocr = files.get("is_ocr", enable_ocr)
            file_page_ranges = files.get("page_ranges", page_ranges)

            file_config = {
                "path": file_path,
                "name": file_name,
                "is_ocr": file_is_ocr,
            }
            if file_page_ranges is not None:
                file_config["page_ranges"] = file_page_ranges

            files_config.append(file_config)
        else:
            raise TypeError(f"files must be string, list, or dict, not {type(files)}")

        # Step 1: Construct API request payload
        files_payload = []
        for file_config in files_config:
            file_payload = {
                "name": file_config["name"],
                "is_ocr": file_config["is_ocr"],
            }
            if "page_ranges" in file_config and file_config["page_ranges"] is not None:
                file_payload["page_ranges"] = file_config["page_ranges"]
            files_payload.append(file_payload)

        payload = {
            "language": language,
            "files": files_payload,
        }

        # Step 2: Get file upload URLs
        response = await self._request("POST", "/api/v4/file-urls/batch", json=payload)

        # Check response
        if (
            "data" not in response
            or "batch_id" not in response["data"]
            or "file_urls" not in response["data"]
        ):
            raise ValueError(f"Failed to get upload URLs: {response}")

        batch_id = response["data"]["batch_id"]
        file_urls = response["data"]["file_urls"]

        if len(file_urls) != len(files_config):
            raise ValueError(
                f"Number of upload URLs ({len(file_urls)}) mismatch with file count ({len(files_config)})"
            )

        config.logger.info(f"Uploading {len(file_urls)} local files")
        config.logger.debug(f"Got upload URLs, batch ID: {batch_id}")

        # Step 3: Upload all files
        uploaded_files = []

        for i, (file_config, upload_url) in enumerate(zip(files_config, file_urls)):
            file_path = file_config["path"]
            if file_path is None:
                raise ValueError(f"File {file_config['name']} has no valid path")

            try:
                with open(file_path, "rb") as f:
                    # IMPORTANT: Do not set Content-Type; let OSS handle it automatically
                    response = requests.put(upload_url, data=f)

                    if response.status_code != 200:
                        raise ValueError(
                            f"File upload failed, status code: {response.status_code}, response: {response.text}"
                        )

                    config.logger.debug(f"File {file_path.name} uploaded successfully")
                    uploaded_files.append(file_path.name)
            except Exception as e:
                raise ValueError(f"File {file_path.name} upload failed: {str(e)}")

        config.logger.info(f"File upload complete, total {len(uploaded_files)} files")

        # Return response with batch_id and uploaded file info
        result = {"data": {"batch_id": batch_id, "uploaded_files": uploaded_files}}

        # For single file case, maintain compatibility with original return format
        if len(uploaded_files) == 1:
            result["data"]["file_name"] = uploaded_files[0]

        return result

    async def get_batch_task_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Get the status of a batch conversion task.

        Args:
            batch_id: ID of the batch task

        Returns:
            dict: Batch task status information
        """
        response = await self._request(
            "GET", f"/api/v4/extract-results/batch/{batch_id}"
        )

        return response

    async def process_file_to_markdown(
        self,
        task_fn,
        task_arg: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        enable_ocr: bool = True,
        output_dir: Optional[str] = None,
        max_retries: int = 180,
        retry_interval: int = 10,
    ) -> Union[str, Dict[str, Any]]:
        """
        Handle end-to-end File to Markdown conversion.

        Args:
            task_fn: Task submission function (submit_file_url_task or submit_file_task)
            task_arg: Task function arguments:
                    - URL string
                    - File path string
                    - Dictionary with file config
                    - List of dictionaries with file configs
            enable_ocr: Whether to enable OCR
            output_dir: Output directory for results
            max_retries: Max status check retries
            retry_interval: Interval between status checks (seconds)

        Returns:
            Union[str, Dict[str, Any]]:
                - Single file: Path to the directory containing the extracted Markdown file
                - Multi-file: {
                    "results": [
                        {
                            "filename": str,
                            "status": str,
                            "content": str,
                            "error_message": str,
                        }
                    ],
                    "extract_dir": str
                }
        """
        try:
            # Submit task - use positional arguments
            task_info = await task_fn(task_arg, enable_ocr)

            # Batch task processing
            batch_id = task_info["data"]["batch_id"]

            # Get names of all uploaded files
            uploaded_files = task_info["data"].get("uploaded_files", [])
            if not uploaded_files and "file_name" in task_info["data"]:
                uploaded_files = [task_info["data"]["file_name"]]

            if not uploaded_files:
                raise ValueError("Could not retrieve uploaded file information")

            config.logger.debug(f"Batch task submitted successfully. Batch ID: {batch_id}")

            # Track processing status for all files
            files_status = {}  # Using file_name as key
            files_download_urls = {}
            failed_files = {}  # Record failed files and error info

            # Prepare output path
            output_path = config.ensure_output_dir(output_dir)

            # Poll for task completion
            for i in range(max_retries):
                status_info = await self.get_batch_task_status(batch_id)

                config.logger.debug(f"Polling result: {status_info}")

                if (
                    "data" not in status_info
                    or "extract_result" not in status_info["data"]
                ):
                    config.logger.error(f"Failed to get batch task status: {status_info}")
                    await asyncio.sleep(retry_interval)
                    continue

                # Check status of all files
                all_done = True
                has_progress = False

                for result in status_info["data"]["extract_result"]:
                    file_name = result.get("file_name")

                    if not file_name:
                        continue

                    # Initialize status if not already recorded
                    if file_name not in files_status:
                        files_status[file_name] = "pending"

                    state = result.get("state")
                    files_status[file_name] = state

                    if state == "done":
                        # Save download link
                        full_zip_url = result.get("full_zip_url")
                        if full_zip_url:
                            files_download_urls[file_name] = full_zip_url
                            config.logger.info(f"File {file_name} processing complete")
                        else:
                            config.logger.debug(
                                f"File {file_name} marked as done but no download link"
                            )
                            all_done = False
                    elif state in ["failed", "error"]:
                        err_msg = result.get("err_msg", "Unknown error")
                        failed_files[file_name] = err_msg
                        config.logger.warning(f"File {file_name} processing failed: {err_msg}")
                        # Continue processing other files
                    else:
                        all_done = False
                        # Display progress info
                        if state == "running" and "extract_progress" in result:
                            has_progress = True
                            progress = result["extract_progress"]
                            extracted = progress.get("extracted_pages", 0)
                            total = progress.get("total_pages", 0)
                            if total > 0:
                                percent = (extracted / total) * 100
                                config.logger.info(
                                    f"Processing progress: {file_name} "
                                    + f"{extracted}/{total} pages "
                                    + f"({percent:.1f}%)"
                                )

                # Check if all files have completed
                expected_file_count = len(uploaded_files)
                processed_file_count = len(files_status)
                completed_file_count = len(files_download_urls) + len(failed_files)

                # Record current status
                config.logger.debug(
                    f"File processing status: all_done={all_done}, "
                    + f"files_status count={processed_file_count}, "
                    + f"uploaded files count={expected_file_count}, "
                    + f"download links count={len(files_download_urls)}, "
                    + f"failed files count={len(failed_files)}"
                )

                # Determine if all files are complete (success or failure)
                if (
                    processed_file_count > 0
                    and processed_file_count >= expected_file_count
                    and completed_file_count >= processed_file_count
                ):
                    if files_download_urls or failed_files:
                        config.logger.info("File processing complete")
                        if failed_files:
                            config.logger.warning(
                                f"{len(failed_files)} files failed to process"
                            )
                        break
                    else:
                        # Should not happen, but for safety
                        all_done = False

                # Show simple wait message if no progress info
                if not has_progress:
                    config.logger.info(f"Waiting for file processing to complete... ({i+1}/{max_retries})")

                await asyncio.sleep(retry_interval)
            else:
                # Timeout case, check if partial results exist
                if not files_download_urls and not failed_files:
                    raise TimeoutError(f"Batch task {batch_id} did not complete in time")
                else:
                    config.logger.warning(
                        "Warning: Some files did not complete in time; " + "proceeding with completed files"
                    )

            # Create main extraction directory
            extract_dir = output_path / batch_id
            extract_dir.mkdir(exist_ok=True)

            # Prepare results list
            results = []

            # Download and unzip results for each successful file
            for file_name, download_url in files_download_urls.items():
                try:
                    config.logger.debug(f"Downloading file processing results: {file_name}")

                    # Extract zip filename from URL as subdirectory name
                    zip_file_name = download_url.split("/")[-1]
                    # Remove .zip extension
                    zip_dir_name = os.path.splitext(zip_file_name)[0]

                    file_extract_dir = extract_dir / zip_dir_name
                    file_extract_dir.mkdir(exist_ok=True)

                    # Download ZIP file
                    zip_path = output_path / f"{batch_id}_{zip_file_name}"

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            download_url,
                            headers={"Authorization": f"Bearer {self.api_key}"},
                        ) as response:
                            response.raise_for_status()
                            with open(zip_path, "wb") as f:
                                f.write(await response.read())

                    # Extract to subfolder
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(file_extract_dir)

                    # Delete ZIP after extraction
                    zip_path.unlink()

                    # Attempt to read Markdown content
                    markdown_content = ""
                    markdown_files = list(file_extract_dir.glob("*.md"))
                    if markdown_files:
                        with open(markdown_files[0], "r", encoding="utf-8") as f:
                            markdown_content = f.read()

                    # Add success result
                    results.append(
                        {
                            "filename": file_name,
                            "status": "success",
                            "content": markdown_content,
                            "extract_path": str(file_extract_dir),
                        }
                    )

                    config.logger.debug(
                        f"Result for file {file_name} extracted to: {file_extract_dir}"
                    )

                except Exception as e:
                    # Download failure, add error result
                    error_msg = f"Failed to download result: {str(e)}"
                    config.logger.error(f"File {file_name} {error_msg}")
                    results.append(
                        {
                            "filename": file_name,
                            "status": "error",
                            "error_message": error_msg,
                        }
                    )

            # Add failed files to results
            for file_name, error_msg in failed_files.items():
                results.append(
                    {
                        "filename": file_name,
                        "status": "error",
                        "error_message": f"Processing failure: {error_msg}",
                    }
                )

            # Output processing statistics
            success_count = len(files_download_urls)
            fail_count = len(failed_files)
            total_count = success_count + fail_count

            config.logger.info("\n=== File Processing Statistics ===")
            config.logger.info(f"Total files: {total_count}")
            config.logger.info(f"Successfully processed: {success_count}")
            config.logger.info(f"Failed to process: {fail_count}")

            if failed_files:
                config.logger.info("\nFailed file details:")
                for file_name, error_msg in failed_files.items():
                    config.logger.info(f"  - {file_name}: {error_msg}")

            if success_count > 0:
                config.logger.info(f"\nResult save directory: {extract_dir}")
            else:
                config.logger.info(f"\nOutput directory: {extract_dir}")

            # Return detailed results
            return {
                "results": results,
                "extract_dir": str(extract_dir),
                "success_count": success_count,
                "fail_count": fail_count,
                "total_count": total_count,
            }

        except Exception as e:
            config.logger.error(f"Processing File to Markdown failed: {str(e)}")
            raise
