"""
VParse Heavy - API Server
Heavy API Server

Provides RESTful API for task submission, query, and management.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
from loguru import logger
import uvicorn
from typing import Optional
from datetime import datetime
import os
import re
import uuid
import json
from minio import Minio

from task_db import TaskDB

# Initialize FastAPI application
app = FastAPI(
    title="VParse Heavy API",
    description="Heavy - Enterprise-grade multi-GPU document parsing service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = TaskDB()

# Configure output directory
OUTPUT_DIR = Path('/tmp/vparse_heavy_output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# MinIO Configuration
MINIO_CONFIG = {
    'endpoint': os.getenv('MINIO_ENDPOINT', ''),
    'access_key': os.getenv('MINIO_ACCESS_KEY', ''),
    'secret_key': os.getenv('MINIO_SECRET_KEY', ''),
    'secure': True,
    'bucket_name': os.getenv('MINIO_BUCKET', '')
}


def get_minio_client():
    """Get MinIO client instance."""
    return Minio(
        endpoint=MINIO_CONFIG['endpoint'],
        access_key=MINIO_CONFIG['access_key'],
        secret_key=MINIO_CONFIG['secret_key'],
        secure=MINIO_CONFIG['secure']
    )


def process_markdown_images(md_content: str, image_dir: Path, upload_images: bool = False):
    """
    Process image references in Markdown.
    
    Args:
        md_content: Markdown content
        image_dir: Directory containing images
        upload_images: Whether to upload images to MinIO and replace links
        
    Returns:
        Processed Markdown content
    """
    if not upload_images:
        return md_content
    
    try:
        minio_client = get_minio_client()
        bucket_name = MINIO_CONFIG['bucket_name']
        minio_endpoint = MINIO_CONFIG['endpoint']
        
        # Find all Markdown-formatted images
        img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        def replace_image(match):
            alt_text = match.group(1)
            image_path = match.group(2)
            
            # Build full local image path
            full_image_path = image_dir / Path(image_path).name
            
            if full_image_path.exists():
                # Get file suffix
                file_extension = full_image_path.suffix
                # Generate UUID as new filename
                new_filename = f"{uuid.uuid4()}{file_extension}"
                
                try:
                    # Upload to MinIO
                    object_name = f"images/{new_filename}"
                    minio_client.fput_object(bucket_name=bucket_name, object_name=object_name, file_path=str(full_image_path))
                    
                    # Generate MinIO access URL
                    scheme = 'https' if MINIO_CONFIG['secure'] else 'http'
                    minio_url = f"{scheme}://{minio_endpoint}/{bucket_name}/{object_name}"
                    
                    # Return HTML-formatted img tag
                    return f'<img src="{minio_url}" alt="{alt_text}">'
                except Exception as e:
                    logger.error(f"Failed to upload image to MinIO: {e}")
                    return match.group(0)  # Keep as is on failure
            
            return match.group(0)
        
        # Replace all image references
        new_content = re.sub(img_pattern, replace_image, md_content)
        return new_content
        
    except Exception as e:
        logger.error(f"Error processing markdown images: {e}")
        return md_content  # Return original content on error


def read_json_file(file_path: Path):
    """
    Read JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data, or None on failure
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON file {file_path}: {e}")
        return None


def get_file_metadata(file_path: Path):
    """
    Get file metadata.

    Args:
        file_path: File path

    Returns:
        Dictionary containing file metadata
    """
    if not file_path.exists():
        return None

    stat = file_path.stat()
    return {
        'size': stat.st_size,
        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


def get_images_info(image_dir: Path, upload_to_minio: bool = False):
    """
    Get information about the image directory.

    Args:
        image_dir: Image directory path
        upload_to_minio: Whether to upload to MinIO

    Returns:
        Dictionary of image information
    """
    if not image_dir.exists() or not image_dir.is_dir():
        return {
            'count': 0,
            'list': [],
            'uploaded_to_minio': False
        }

    # Supported image formats
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}
    image_files = [f for f in image_dir.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

    images_list = []

    for img_file in sorted(image_files):
        img_info = {
            'name': img_file.name,
            'size': img_file.stat().st_size,
            'path': str(img_file.relative_to(image_dir.parent))
        }

        # If upload to MinIO is required
        if upload_to_minio:
            try:
                minio_client = get_minio_client()
                bucket_name = MINIO_CONFIG['bucket_name']
                minio_endpoint = MINIO_CONFIG['endpoint']

                # Generate UUID as new filename
                file_extension = img_file.suffix
                new_filename = f"{uuid.uuid4()}{file_extension}"
                object_name = f"images/{new_filename}"

                # Upload to MinIO
                minio_client.fput_object(bucket_name=bucket_name, object_name=object_name, file_path=str(img_file))

                # Generate access URL
                scheme = 'https' if MINIO_CONFIG['secure'] else 'http'
                img_info['url'] = f"{scheme}://{minio_endpoint}/{bucket_name}/{object_name}"

            except Exception as e:
                logger.error(f"Failed to upload image {img_file.name} to MinIO: {e}")
                img_info['url'] = None

        images_list.append(img_info)

    return {
        'count': len(images_list),
        'list': images_list,
        'uploaded_to_minio': upload_to_minio
    }


@app.get("/")
async def root():
    """API root path"""
    return {
        "service": "VParse Heavy",
        "version": "1.0.0",
        "description": "Heavy - Enterprise-grade multi-GPU document parsing service",
        "docs": "/docs"
    }


@app.post("/api/v1/tasks/submit")
async def submit_task(
    file: UploadFile = File(..., description="Document file: PDF/Images (VParse) or Office/HTML/Text (MarkItDown)"),
    backend: str = Form('pipeline', description="Processing backend: pipeline/vlm-transformers/vlm-vllm-engine"),
    lang: str = Form('ch', description="Language: ch/en/korean/japan etc."),
    method: str = Form('auto', description="Parsing method: auto/txt/ocr"),
    formula_enable: bool = Form(True, description="Whether to enable formula recognition"),
    table_enable: bool = Form(True, description="Whether to enable table recognition"),
    priority: int = Form(0, description="Priority, higher numbers mean higher priority"),
):
    """
    Submit document parsing task.
    
    Returns task_id immediately; tasks are processed asynchronously.
    """
    try:
        # Save uploaded file to temporary directory
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
        
        # Stream file to disk to avoid high memory usage
        while True:
            chunk = await file.read(1 << 23)  # 8MB chunks
            if not chunk:
                break
            temp_file.write(chunk)
        
        temp_file.close()
        
        # Create task
        task_id = db.create_task(
            file_name=file.filename,
            file_path=temp_file.name,
            backend=backend,
            options={
                'lang': lang,
                'method': method,
                'formula_enable': formula_enable,
                'table_enable': table_enable,
            },
            priority=priority
        )
        
        logger.info(f"✅ Task submitted: {task_id} - {file.filename} (priority: {priority})")
        
        return {
            'success': True,
            'task_id': task_id,
            'status': 'pending',
            'message': 'Task submitted successfully',
            'file_name': file.filename,
            'created_at': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_id}/data")
async def get_task_data(
    task_id: str,
    include_fields: str = Query(
        "md,content_list,middle_json,model_output,images",
        description="Fields to return, comma-separated: md,content_list,middle_json,model_output,images,layout_pdf,span_pdf,origin_pdf"
    ),
    upload_images: bool = Query(False, description="Upload images to MinIO and return URLs"),
    include_metadata: bool = Query(True, description="Include file metadata")
):
    """
    Retrieve parsing data for a task on demand.

    Supports flexible retrieval of parsed data from VParse, including:
    - Markdown content
    - Content List JSON (Structured content list)
    - Middle JSON (Intermediate results)
    - Model Output JSON (Raw model output)
    - Image list
    - Other auxiliary files (layout PDF, span PDF, origin PDF)

    Select fields to return via the include_fields parameter
    """
    # Get task information
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build base response
    response = {
        'success': True,
        'task_id': task_id,
        'status': task['status'],
        'file_name': task['file_name'],
        'backend': task['backend'],
        'created_at': task['created_at'],
        'completed_at': task['completed_at']
    }

    # If task is not completed, return status only
    if task['status'] != 'completed':
        response['message'] = f"Task is in {task['status']} status, data not available yet"
        return response

    # Check result path
    if not task['result_path']:
        response['message'] = 'Task completed but result files have been cleaned up'
        return response

    result_dir = Path(task['result_path'])
    if not result_dir.exists():
        response['message'] = 'Result directory does not exist'
        return response

    # Parse requested fields
    fields = [f.strip() for f in include_fields.split(',')]

    # Initialize data field
    response['data'] = {}  # type: ignore

    logger.info(f"📦 Getting complete data for task {task_id}, fields: {fields}")

    # Find files (Recursive search, VParse output structure: task_id/filename/auto/*.md)
    try:
        # 1. Process Markdown file
        if 'md' in fields:
            md_files = list(result_dir.rglob('*.md'))
            # Exclude md files with special suffixes
            md_files = [f for f in md_files if not any(f.stem.endswith(suffix) for suffix in ['_layout', '_span', '_origin'])] 

            if md_files:
                md_file = md_files[0]
                logger.info(f"📄 Reading markdown file: {md_file}")

                with open(md_file, 'r', encoding='utf-8') as f:
                    md_content = f.read()

                # Process images if upload is required
                image_dir = md_file.parent / 'images'
                if upload_images and image_dir.exists():
                    md_content = process_markdown_images(md_content, image_dir, upload_images)

                response['data']['markdown'] = {
                    'content': md_content,
                    'file_name': md_file.name
                }

                if include_metadata:
                    metadata = get_file_metadata(md_file)
                    if metadata:
                        response['data']['markdown']['metadata'] = metadata

        # 2. Process Content List JSON
        if 'content_list' in fields:
            content_list_files = list(result_dir.rglob('*_content_list.json'))
            if content_list_files:
                content_list_file = content_list_files[0]
                logger.info(f"📄 Reading content list file: {content_list_file}")

                content_data = read_json_file(content_list_file)
                if content_data is not None:
                    response['data']['content_list'] = {
                        'content': content_data,
                        'file_name': content_list_file.name
                    }

                    if include_metadata:
                        metadata = get_file_metadata(content_list_file)
                        if metadata:
                            response['data']['content_list']['metadata'] = metadata

        # 3. Process Middle JSON
        if 'middle_json' in fields:
            middle_json_files = list(result_dir.rglob('*_middle.json'))
            if middle_json_files:
                middle_json_file = middle_json_files[0]
                logger.info(f"📄 Reading middle json file: {middle_json_file}")

                middle_data = read_json_file(middle_json_file)
                if middle_data is not None:
                    response['data']['middle_json'] = {
                        'content': middle_data,
                        'file_name': middle_json_file.name
                    }

                    if include_metadata:
                        metadata = get_file_metadata(middle_json_file)
                        if metadata:
                            response['data']['middle_json']['metadata'] = metadata

        # 4. Process Model Output JSON
        if 'model_output' in fields:
            model_output_files = list(result_dir.rglob('*_model.json'))
            if model_output_files:
                model_output_file = model_output_files[0]
                logger.info(f"📄 Reading model output file: {model_output_file}")

                model_data = read_json_file(model_output_file)
                if model_data is not None:
                    response['data']['model_output'] = {
                        'content': model_data,
                        'file_name': model_output_file.name
                    }

                    if include_metadata:
                        metadata = get_file_metadata(model_output_file)
                        if metadata:
                            response['data']['model_output']['metadata'] = metadata

        # 5. Process Images
        if 'images' in fields:
            image_dirs = list(result_dir.rglob('images'))
            if image_dirs:
                image_dir = image_dirs[0]
                logger.info(f"🖼️  Getting images info from: {image_dir}")

                images_info = get_images_info(image_dir, upload_images)
                response['data']['images'] = images_info

        # 6. Process Layout PDF
        if 'layout_pdf' in fields:
            layout_pdf_files = list(result_dir.rglob('*_layout.pdf'))
            if layout_pdf_files:
                layout_pdf_file = layout_pdf_files[0]
                response['data']['layout_pdf'] = {
                    'file_name': layout_pdf_file.name,
                    'path': str(layout_pdf_file.relative_to(result_dir))
                }

                if include_metadata:
                    metadata = get_file_metadata(layout_pdf_file)
                    if metadata:
                        response['data']['layout_pdf']['metadata'] = metadata

        # 7. Process Span PDF
        if 'span_pdf' in fields:
            span_pdf_files = list(result_dir.rglob('*_span.pdf'))
            if span_pdf_files:
                span_pdf_file = span_pdf_files[0]
                response['data']['span_pdf'] = {
                    'file_name': span_pdf_file.name,
                    'path': str(span_pdf_file.relative_to(result_dir))
                }

                if include_metadata:
                    metadata = get_file_metadata(span_pdf_file)
                    if metadata:
                        response['data']['span_pdf']['metadata'] = metadata

        # 8. Process Origin PDF
        if 'origin_pdf' in fields:
            origin_pdf_files = list(result_dir.rglob('*_origin.pdf'))
            if origin_pdf_files:
                origin_pdf_file = origin_pdf_files[0]
                response['data']['origin_pdf'] = {
                    'file_name': origin_pdf_file.name,
                    'path': str(origin_pdf_file.relative_to(result_dir))
                }

                if include_metadata:
                    metadata = get_file_metadata(origin_pdf_file)
                    if metadata:
                        response['data']['origin_pdf']['metadata'] = metadata

        logger.info(f"✅ Complete data retrieved successfully for task {task_id}")

    except Exception as e:
        logger.error(f"❌ Failed to get complete data for task {task_id}: {e}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")  

    return response


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    upload_images: bool = Query(False, description="Upload images to MinIO and replace URLs (only if completed)")
):
    """
    Retrieve task status and details.
    
    Returns parsed Markdown content (data field) automatically upon completion.
    """
    task = db.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    response = {
        'success': True,
        'task_id': task_id,
        'status': task['status'],
        'file_name': task['file_name'],
        'backend': task['backend'],
        'priority': task['priority'],
        'error_message': task['error_message'],
        'created_at': task['created_at'],
        'started_at': task['started_at'],
        'completed_at': task['completed_at'],
        'worker_id': task['worker_id'],
        'retry_count': task['retry_count']
    }
    logger.info(f"✅ Task status: {task['status']} - (result_path: {task['result_path']})")
    
    # If task is completed, attempt to return parsed content
    if task['status'] == 'completed':
        if not task['result_path']:
            # Result files cleaned up
            response['data'] = None
            response['message'] = 'Task completed but result files have been cleaned up'
            return response
        
        result_dir = Path(task['result_path'])
        logger.info(f"📂 Checking result directory: {result_dir}")
        
        if result_dir.exists():
            logger.info(f"✅ Result directory exists")
            # Recursively search for Markdown files (VParse output structure: task_id/filename/auto/*.md)
            md_files = list(result_dir.rglob('*.md'))
            logger.info(f"📄 Found {len(md_files)} markdown files: {[f.relative_to(result_dir) for f in md_files]}")
            
            if md_files:
                try:
                    # Read Markdown content
                    md_file = md_files[0]
                    logger.info(f"📖 Reading markdown file: {md_file}")
                    with open(md_file, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                    
                    logger.info(f"✅ Markdown content loaded, length: {len(md_content)} characters")
                    
                    # Find image directory
                    image_dir = md_file.parent / 'images'
                    
                    # Process images if needed
                    if upload_images and image_dir.exists():
                        logger.info(f"🖼️  Processing images for task {task_id}, upload_images={upload_images}")
                        md_content = process_markdown_images(md_content, image_dir, upload_images)
                    
                    # Add data field
                    response['data'] = {
                        'markdown_file': md_file.name,
                        'content': md_content,
                        'images_uploaded': upload_images,
                        'has_images': image_dir.exists() if not upload_images else None
                    }
                    logger.info(f"✅ Response data field added successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to read markdown content: {e}")
                    logger.exception(e)
                    # Failure to read doesn't affect status query
                    response['data'] = None
            else:
                logger.warning(f"⚠️  No markdown files found in {result_dir}")
        else:
            logger.error(f"❌ Result directory does not exist: {result_dir}")
    elif task['status'] == 'completed':
        logger.warning(f"⚠️  Task completed but result_path is empty")
    else:
        logger.info(f"ℹ️  Task status is {task['status']}, skipping content loading")
    
    return response


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel task (pending status only).
    """
    task = db.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task['status'] == 'pending':
        db.update_task_status(task_id, 'cancelled')
        
        # Delete temporary file
        file_path = Path(task['file_path'])
        if file_path.exists():
            file_path.unlink()
        
        logger.info(f"⏹️  Task cancelled: {task_id}")
        return {
            'success': True,
            'message': 'Task cancelled successfully'
        }
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel task in {task['status']} status"
        )


@app.get("/api/v1/queue/stats")
async def get_queue_stats():
    """
    Get queue statistics.
    """
    stats = db.get_queue_stats()
    
    return {
        'success': True,
        'stats': stats,
        'total': sum(stats.values()),
        'timestamp': datetime.now().isoformat()
    }


@app.get("/api/v1/queue/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter status: pending/processing/completed/failed"),
    limit: int = Query(100, description="Result limit", le=1000)
):
    """
    Retrieve task list.
    """
    if status:
        tasks = db.get_tasks_by_status(status, limit)
    else:
        # Return all tasks
        with db.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM tasks 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            tasks = [dict(row) for row in cursor.fetchall()]
    
    return {
        'success': True,
        'count': len(tasks),
        'tasks': tasks
    }


@app.post("/api/v1/admin/cleanup")
async def cleanup_old_tasks(days: int = Query(7, description="Clean up tasks older than N days")):
    """
    Clean up old task records (Admin interface).
    """
    deleted_count = db.cleanup_old_tasks(days)
    
    logger.info(f"🧹 Cleaned up {deleted_count} old tasks")
    
    return {
        'success': True,
        'deleted_count': deleted_count,
        'message': f'Cleaned up tasks older than {days} days'
    }


@app.post("/api/v1/admin/reset-stale")
async def reset_stale_tasks(timeout_minutes: int = Query(60, description="Timeout in minutes")):
    """
    Reset timed-out processing tasks (Admin interface).
    """
    reset_count = db.reset_stale_tasks(timeout_minutes)
    
    logger.info(f"🔄 Reset {reset_count} stale tasks")
    
    return {
        'success': True,
        'reset_count': reset_count,
        'message': f'Reset tasks processing for more than {timeout_minutes} minutes'
    }


@app.get("/api/v1/health")
async def health_check_endpoint():
    """
    Health check endpoint.
    """
    try:
        # Check database connection
        stats = db.get_queue_stats()
        
        return {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'queue_stats': stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                'status': 'unhealthy',
                'error': str(e)
            }
        )


if __name__ == '__main__':
    # Read port from environment, default to 8000
    api_port = int(os.getenv('API_PORT', '8000'))
    
    logger.info("🚀 Starting VParse Heavy API Server...")
    logger.info(f"📖 API Documentation: http://localhost:{api_port}/docs")
    
    uvicorn.run(
        app, 
        host='0.0.0.0', 
        port=api_port,
        log_level='info'
    )
