# Copyright (c) Opendatalab. All rights reserved.
import os
import signal
import time
from io import BytesIO

import numpy as np
import pypdfium2 as pdfium
from loguru import logger
from PIL import Image, ImageOps

from vparse.data.data_reader_writer import FileBasedDataWriter
from vparse.utils.check_sys_env import is_windows_environment
from vparse.utils.os_env_config import get_load_images_timeout, get_load_images_threads
from vparse.utils.pdf_reader import image_to_b64str, image_to_bytes, page_to_image
from vparse.utils.enum_class import ImageType
from vparse.utils.hash_utils import str_sha256
from vparse.utils.pdf_page_id import get_end_page_id

from concurrent.futures import ProcessPoolExecutor, wait, ALL_COMPLETED


def pdf_page_to_image(page: pdfium.PdfPage, dpi=200, image_type=ImageType.PIL) -> dict:
    """Convert pdfium.PdfDocument to image, Then convert the image to base64.

    Args:
        page (_type_): pdfium.PdfPage
        dpi (int, optional): reset the dpi of dpi. Defaults to 200.
        image_type (ImageType, optional): The type of image to return. Defaults to ImageType.PIL.

    Returns:
        dict:  {'img_base64': str, 'img_pil': pil_img, 'scale': float }
    """
    pil_img, scale = page_to_image(page, dpi=dpi)
    image_dict = {
        "scale": scale,
    }
    if image_type == ImageType.BASE64:
        image_dict["img_base64"] = image_to_b64str(pil_img)
    else:
        image_dict["img_pil"] = pil_img

    return image_dict


def _load_images_from_pdf_worker(
    pdf_bytes, dpi, start_page_id, end_page_id, image_type
):
    """Wrapper function for process pool"""
    return load_images_from_pdf_core(
        pdf_bytes, dpi, start_page_id, end_page_id, image_type
    )


def load_images_from_pdf(
    pdf_bytes: bytes,
    dpi=200,
    start_page_id=0,
    end_page_id=None,
    image_type=ImageType.PIL,
    timeout=None,
    threads=None,
):
    """PDF to image function with timeout control, supports multi-process acceleration

    Args:
        pdf_bytes (bytes): PDF file bytes
        dpi (int, optional): reset the dpi of dpi. Defaults to 200.
        start_page_id (int, optional): Start page number. Defaults to 0.
        end_page_id (int | None, optional): End page number. Defaults to None.
        image_type (ImageType, optional): Image type. Defaults to ImageType.PIL.
        timeout (int | None, optional): Timeout in seconds. If None, reads from VPARSE_PDF_RENDER_TIMEOUT; defaults to 300 seconds.
        threads (int): Number of threads. If None, reads from VPARSE_PDF_RENDER_THREADS; defaults to 4.

    Raises:
        TimeoutError: Raised when conversion times out
    """
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    if is_windows_environment():
        # Do not use multi-processing in Windows environment
        return load_images_from_pdf_core(
            pdf_bytes,
            dpi,
            start_page_id,
            get_end_page_id(end_page_id, len(pdf_doc)),
            image_type,
        ), pdf_doc
    else:
        if timeout is None:
            timeout = get_load_images_timeout()
        if threads is None:
            threads = get_load_images_threads()

        end_page_id = get_end_page_id(end_page_id, len(pdf_doc))

        # Calculate total pages
        total_pages = end_page_id - start_page_id + 1

        # Actual number of processes used does not exceed total pages
        actual_threads = min(os.cpu_count() or 1, threads, total_pages)

        # Group page ranges based on the actual number of processes
        pages_per_thread = max(1, total_pages // actual_threads)
        page_ranges = []

        for i in range(actual_threads):
            range_start = start_page_id + i * pages_per_thread
            if i == actual_threads - 1:
                # The last process handles all remaining pages
                range_end = end_page_id
            else:
                range_end = start_page_id + (i + 1) * pages_per_thread - 1

            page_ranges.append((range_start, range_end))

        logger.debug(f"PDF to images using {actual_threads} processes, page ranges: {page_ranges}")

        executor = ProcessPoolExecutor(max_workers=actual_threads)
        try:
            # Submit all tasks
            futures = []
            future_to_range = {}
            for range_start, range_end in page_ranges:
                future = executor.submit(
                    _load_images_from_pdf_worker,
                    pdf_bytes,
                    dpi,
                    range_start,
                    range_end,
                    image_type,
                )
                futures.append(future)
                future_to_range[future] = range_start

            # Use wait() to set a single global timeout
            done, not_done = wait(futures, timeout=timeout, return_when=ALL_COMPLETED)

            # Check for unfinished tasks (timeout case)
            if not_done:
                # Timeout: Forcefully terminate all child processes
                _terminate_executor_processes(executor)
                pdf_doc.close()
                raise TimeoutError(f"PDF to images conversion timeout after {timeout}s")

            # All tasks completed, collect results
            all_results = []
            for future in futures:
                range_start = future_to_range[future]
                # Timeout is not needed here as tasks are completed
                images_list = future.result()
                all_results.append((range_start, images_list))

            # Sort by start page ID and merge results
            all_results.sort(key=lambda x: x[0])
            images_list = []
            for _, imgs in all_results:
                images_list.extend(imgs)

            return images_list, pdf_doc

        except Exception as e:
            # Ensure child processes are cleaned up on any exception
            _terminate_executor_processes(executor)
            pdf_doc.close()
            if isinstance(e, TimeoutError):
                raise
            raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _terminate_executor_processes(executor):
    """Forcefully terminate all child processes in ProcessPoolExecutor"""
    if hasattr(executor, '_processes'):
        for pid, process in executor._processes.items():
            if process.is_alive():
                try:
                    # Send SIGTERM first to allow graceful exit
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass

        # Give child processes some time to respond to SIGTERM
        time.sleep(0.1)

        # Send SIGKILL to still living processes to force termination
        for pid, process in executor._processes.items():
            if process.is_alive():
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass


def load_images_from_pdf_core(
    pdf_bytes: bytes,
    dpi=200,
    start_page_id=0,
    end_page_id=None,
    image_type=ImageType.PIL,  # PIL or BASE64
):
    images_list = []
    pdf_doc = pdfium.PdfDocument(pdf_bytes)
    pdf_page_num = len(pdf_doc)
    end_page_id = get_end_page_id(end_page_id, pdf_page_num)

    for index in range(start_page_id, end_page_id + 1):
        # logger.debug(f"Converting page {index}/{pdf_page_num} to image")
        page = pdf_doc[index]
        image_dict = pdf_page_to_image(page, dpi=dpi, image_type=image_type)
        images_list.append(image_dict)

    pdf_doc.close()

    return images_list


def cut_image(
    bbox: tuple,
    page_num: int,
    page_pil_img,
    return_path,
    image_writer: FileBasedDataWriter,
    scale=2,
):
    """Crop a jpg image from page number page_num based on bbox, return the image path. save_path: should support both S3 and local.
    Images are stored in save_path with the filename:
    {page_num}_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}.jpg, numbers in bbox are rounded to integers."""

    # Concatenate filename
    filename = f"{page_num}_{int(bbox[0])}_{int(bbox[1])}_{int(bbox[2])}_{int(bbox[3])}"

    # Old version returns path without bucket
    img_path = f"{return_path}_{filename}" if return_path is not None else None

    # New version generates flattened path
    img_hash256_path = f"{str_sha256(img_path)}.jpg"
    # img_hash256_path = f'{img_path}.jpg'

    crop_img = get_crop_img(bbox, page_pil_img, scale=scale)

    img_bytes = image_to_bytes(crop_img, image_format="JPEG")

    image_writer.write(img_hash256_path, img_bytes)
    return img_hash256_path



def get_crop_img(bbox: tuple, pil_img, scale=2):
    scale_bbox = (
        int(bbox[0] * scale),
        int(bbox[1] * scale),
        int(bbox[2] * scale),
        int(bbox[3] * scale),
    )
    return pil_img.crop(scale_bbox)


def get_crop_np_img(bbox: tuple, input_img, scale=2):
    if isinstance(input_img, Image.Image):
        np_img = np.asarray(input_img)
    elif isinstance(input_img, np.ndarray):
        np_img = input_img
    else:
        raise ValueError("Input must be a pillow object or a numpy array.")

    scale_bbox = (
        int(bbox[0] * scale),
        int(bbox[1] * scale),
        int(bbox[2] * scale),
        int(bbox[3] * scale),
    )

    return np_img[scale_bbox[1] : scale_bbox[3], scale_bbox[0] : scale_bbox[2]]


def images_bytes_to_pdf_bytes(image_bytes):
    # Memory buffer
    pdf_buffer = BytesIO()

    # Load and convert all images to RGB mode
    image = Image.open(BytesIO(image_bytes))
    # Automatically correct orientation based on EXIF (handles photos with Orientation tags)
    image = ImageOps.exif_transpose(image) or image
    # Convert only when necessary
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Save the first image as PDF, append others
    image.save(
        pdf_buffer,
        format="PDF",
        # save_all=True
    )

    # Get PDF bytes and reset pointer (optional)
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()
    return pdf_bytes
