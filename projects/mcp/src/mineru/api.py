"""API client for the MinerU MCP service."""

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
class MinerUClient:
    """Client for submitting conversion jobs to the MinerU API."""

    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize the client from explicit values or environment variables."""
        self.api_base = api_base or config.MINERU_API_BASE
        self.api_key = api_key or config.MINERU_API_KEY

        if not self.api_key:
            raise ValueError(
                "MinerU API key (MINERU_API_KEY) is not set.\n"
                "Set MINERU_API_KEY in the environment, for example:\n"
                "  export MINERU_API_KEY='your_actual_api_key'\n"
                "Or define it in the project root `.env` file."
            )

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Send an authenticated request to the MinerU API."""
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        if "headers" in kwargs:
            kwargs["headers"].update(headers)
        else:
            kwargs["headers"] = headers

        log_kwargs = kwargs.copy()
        if "headers" in log_kwargs and "Authorization" in log_kwargs["headers"]:
            log_kwargs["headers"] = log_kwargs["headers"].copy()
            log_kwargs["headers"]["Authorization"] = "Bearer ****"

        config.logger.debug(f"API request: {method} {url}")
        config.logger.debug(f"Request kwargs: {log_kwargs}")

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                response_json = await response.json()

                config.logger.debug(f"API response: {response_json}")

                return response_json

    async def submit_file_url_task(
        self,
        urls: Union[str, List[Union[str, Dict[str, Any]]], Dict[str, Any]],
        enable_ocr: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit one or more file URLs for conversion."""
        url_count = 1
        if isinstance(urls, list):
            url_count = len(urls)
        config.logger.debug(
            f"submit_file_url_task called with {url_count} URL(s), "
            + f"ocr={enable_ocr}, "
            + f"language={language}"
        )

        urls_config = []

        if isinstance(urls, str):
            urls_config.append(
                {"url": urls, "is_ocr": enable_ocr, "page_ranges": page_ranges}
            )

        elif isinstance(urls, list):
            for url_item in urls:
                if isinstance(url_item, str):
                    urls_config.append(
                        {
                            "url": url_item,
                            "is_ocr": enable_ocr,
                            "page_ranges": page_ranges,
                        }
                    )

                elif isinstance(url_item, dict):
                    if "url" not in url_item:
                        raise ValueError(f"URL config must include 'url': {url_item}")

                    url_is_ocr = url_item.get("is_ocr", enable_ocr)
                    url_page_ranges = url_item.get("page_ranges", page_ranges)

                    url_config = {"url": url_item["url"], "is_ocr": url_is_ocr}
                    if url_page_ranges is not None:
                        url_config["page_ranges"] = url_page_ranges

                    urls_config.append(url_config)
                else:
                    raise TypeError(f"Unsupported URL config type: {type(url_item)}")
        elif isinstance(urls, dict):
            if "url" not in urls:
                raise ValueError(f"URL config must include 'url': {urls}")

            url_is_ocr = urls.get("is_ocr", enable_ocr)
            url_page_ranges = urls.get("page_ranges", page_ranges)

            url_config = {"url": urls["url"], "is_ocr": url_is_ocr}
            if url_page_ranges is not None:
                url_config["page_ranges"] = url_page_ranges

            urls_config.append(url_config)
        else:
            raise TypeError(f"urls must be a string, list, or dict, not {type(urls)}")

        files_payload = urls_config

        payload = {
            "language": language,
            "files": files_payload,
        }

        response = await self._request(
            "POST", "/api/v4/extract/task/batch", json=payload
        )

        if "data" not in response or "batch_id" not in response["data"]:
            raise ValueError(f"Failed to submit batch URL task: {response}")

        batch_id = response["data"]["batch_id"]

        config.logger.info(f"Started processing {len(urls_config)} file URL(s)")
        config.logger.debug(f"Batch URL task submitted successfully, batch ID: {batch_id}")

        result = {
            "data": {
                "batch_id": batch_id,
                "uploaded_files": [url_config.get("url") for url_config in urls_config],
            }
        }

        if len(urls_config) == 1:
            url = urls_config[0]["url"]
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
        """Submit one or more local files for conversion."""
        file_count = 1
        if isinstance(files, list):
            file_count = len(files)
        config.logger.debug(
            f"submit_file_task called with {file_count} file(s), "
            + f"ocr={enable_ocr}, "
            + f"language={language}"
        )

        files_config = []

        if isinstance(files, str):
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
            for file_item in enumerate(files):
                file_item = file_item[1]
                if isinstance(file_item, str):
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
                    if "path" not in file_item and "name" not in file_item:
                        raise ValueError(
                            f"File config must include 'path' or 'name': {file_item}"
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
            if "path" not in files and "name" not in files:
                raise ValueError(f"File config must include 'path' or 'name': {files}")

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
            raise TypeError(f"files must be a string, list, or dict, not {type(files)}")

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

        response = await self._request("POST", "/api/v4/file-urls/batch", json=payload)

        if (
            "data" not in response
            or "batch_id" not in response["data"]
            or "file_urls" not in response["data"]
        ):
            raise ValueError(f"Failed to fetch upload URLs: {response}")

        batch_id = response["data"]["batch_id"]
        file_urls = response["data"]["file_urls"]

        if len(file_urls) != len(files_config):
            raise ValueError(
                f"Upload URL count ({len(file_urls)}) does not match file count ({len(files_config)})"
            )

        config.logger.info(f"Starting upload for {len(file_urls)} local file(s)")
        config.logger.debug(f"Upload URLs fetched successfully, batch ID: {batch_id}")

        uploaded_files = []

        for file_config, upload_url in zip(files_config, file_urls):
            file_path = file_config["path"]
            if file_path is None:
                raise ValueError(f"File {file_config['name']} does not have a valid path")

            try:
                with open(file_path, "rb") as f:
                    response = requests.put(upload_url, data=f)

                    if response.status_code != 200:
                        raise ValueError(
                            f"File upload failed with status {response.status_code}: {response.text}"
                        )

                    config.logger.debug(f"Uploaded file {file_path.name}")
                    uploaded_files.append(file_path.name)
            except Exception as e:
                raise ValueError(f"Failed to upload file {file_path.name}: {str(e)}")

        config.logger.info(f"Finished uploading {len(uploaded_files)} file(s)")

        result = {"data": {"batch_id": batch_id, "uploaded_files": uploaded_files}}

        if len(uploaded_files) == 1:
            result["data"]["file_name"] = uploaded_files[0]

        return result

    async def get_batch_task_status(self, batch_id: str) -> Dict[str, Any]:
        """Fetch batch conversion status."""
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
        """Submit a task, poll for completion, then download extracted results."""
        try:
            task_info = await task_fn(task_arg, enable_ocr)
            batch_id = task_info["data"]["batch_id"]
            uploaded_files = task_info["data"].get("uploaded_files", [])
            if not uploaded_files and "file_name" in task_info["data"]:
                uploaded_files = [task_info["data"]["file_name"]]

            if not uploaded_files:
                raise ValueError("Could not determine which files were submitted")

            config.logger.debug(f"Batch task submitted successfully. Batch ID: {batch_id}")

            files_status = {}
            files_download_urls = {}
            failed_files = {}

            output_path = config.ensure_output_dir(output_dir)

            for i in range(max_retries):
                status_info = await self.get_batch_task_status(batch_id)

                config.logger.debug(f"Polling result: {status_info}")

                if (
                    "data" not in status_info
                    or "extract_result" not in status_info["data"]
                ):
                    config.logger.error(f"Failed to fetch batch task status: {status_info}")
                    await asyncio.sleep(retry_interval)
                    continue

                all_done = True
                has_progress = False

                for result in status_info["data"]["extract_result"]:
                    file_name = result.get("file_name")

                    if not file_name:
                        continue

                    if file_name not in files_status:
                        files_status[file_name] = "pending"

                    state = result.get("state")
                    files_status[file_name] = state

                    if state == "done":
                        full_zip_url = result.get("full_zip_url")
                        if full_zip_url:
                            files_download_urls[file_name] = full_zip_url
                            config.logger.info(f"File {file_name} completed")
                        else:
                            config.logger.debug(
                                f"File {file_name} is marked done but has no download URL"
                            )
                            all_done = False
                    elif state in ["failed", "error"]:
                        err_msg = result.get("err_msg", "Unknown error")
                        failed_files[file_name] = err_msg
                        config.logger.warning(f"File {file_name} failed: {err_msg}")
                    else:
                        all_done = False
                        if state == "running" and "extract_progress" in result:
                            has_progress = True
                            progress = result["extract_progress"]
                            extracted = progress.get("extracted_pages", 0)
                            total = progress.get("total_pages", 0)
                            if total > 0:
                                percent = (extracted / total) * 100
                                config.logger.info(
                                    f"Progress: {file_name} "
                                    + f"{extracted}/{total} pages "
                                    + f"({percent:.1f}%)"
                                )

                expected_file_count = len(uploaded_files)
                processed_file_count = len(files_status)
                completed_file_count = len(files_download_urls) + len(failed_files)

                config.logger.debug(
                    f"File status: all_done={all_done}, "
                    + f"tracked={processed_file_count}, "
                    + f"uploaded={expected_file_count}, "
                    + f"download_urls={len(files_download_urls)}, "
                    + f"failed={len(failed_files)}"
                )

                if (
                    processed_file_count > 0
                    and processed_file_count >= expected_file_count
                    and completed_file_count >= processed_file_count
                ):
                    if files_download_urls or failed_files:
                        config.logger.info("File processing finished")
                        if failed_files:
                            config.logger.warning(f"{len(failed_files)} file(s) failed")
                        break
                    else:
                        all_done = False

                if not has_progress:
                    config.logger.info(f"Waiting for files to finish... ({i+1}/{max_retries})")

                await asyncio.sleep(retry_interval)
            else:
                if not files_download_urls and not failed_files:
                    raise TimeoutError(f"Batch task {batch_id} did not finish in time")
                else:
                    config.logger.warning(
                        "Some files did not finish in time; continuing with completed results"
                    )

            extract_dir = output_path / batch_id
            extract_dir.mkdir(exist_ok=True)

            results = []

            for file_name, download_url in files_download_urls.items():
                try:
                    config.logger.debug(f"Downloading results for {file_name}")

                    zip_file_name = download_url.split("/")[-1]
                    zip_dir_name = os.path.splitext(zip_file_name)[0]

                    file_extract_dir = extract_dir / zip_dir_name
                    file_extract_dir.mkdir(exist_ok=True)

                    zip_path = output_path / f"{batch_id}_{zip_file_name}"

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            download_url,
                            headers={"Authorization": f"Bearer {self.api_key}"},
                        ) as response:
                            response.raise_for_status()
                            with open(zip_path, "wb") as f:
                                f.write(await response.read())

                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(file_extract_dir)

                    zip_path.unlink()

                    markdown_content = ""
                    markdown_files = list(file_extract_dir.glob("*.md"))
                    if markdown_files:
                        with open(markdown_files[0], "r", encoding="utf-8") as f:
                            markdown_content = f.read()

                    results.append(
                        {
                            "filename": file_name,
                            "status": "success",
                            "content": markdown_content,
                            "extract_path": str(file_extract_dir),
                        }
                    )

                    config.logger.debug(
                        f"Extracted results for {file_name} to: {file_extract_dir}"
                    )

                except Exception as e:
                    error_msg = f"Failed to download results: {str(e)}"
                    config.logger.error(f"File {file_name}: {error_msg}")
                    results.append(
                        {
                            "filename": file_name,
                            "status": "error",
                            "error_message": error_msg,
                        }
                    )

            for file_name, error_msg in failed_files.items():
                results.append(
                    {
                        "filename": file_name,
                        "status": "error",
                        "error_message": f"Processing failed: {error_msg}",
                    }
                )

            success_count = len(files_download_urls)
            fail_count = len(failed_files)
            total_count = success_count + fail_count

            config.logger.info("\n=== File Processing Summary ===")
            config.logger.info(f"Total files: {total_count}")
            config.logger.info(f"Succeeded: {success_count}")
            config.logger.info(f"Failed: {fail_count}")

            if failed_files:
                config.logger.info("\nFailed files:")
                for file_name, error_msg in failed_files.items():
                    config.logger.info(f"  - {file_name}: {error_msg}")

            if success_count > 0:
                config.logger.info(f"\nResults saved to: {extract_dir}")
            else:
                config.logger.info(f"\nOutput directory: {extract_dir}")

            return {
                "results": results,
                "extract_dir": str(extract_dir),
                "success_count": success_count,
                "fail_count": fail_count,
                "total_count": total_count,
            }

        except Exception as e:
            config.logger.error(f"Failed to process file-to-Markdown conversion: {str(e)}")
            raise
