# VParse Heavy (Heavy)

> Heavy - Enterprise-grade Multi-GPU Document Parsing Service  
> The optimal solution combining SQLite task queue + LitServe GPU load balancing

## 🌟 Core Features

### High-Performance Architecture
- ✅ **Worker Auto-Polling** - 0.5s response time; no scheduler trigger required.
- ✅ **Concurrency Safe** - Atomic operations prevent duplicate tasks; supports multiple concurrent workers.
- ✅ **GPU Load Balancing** - LitServe handles automatic scheduling, avoiding VRAM conflicts.
- ✅ **Multi-GPU Isolation** - Each process uses only its assigned GPU, eliminating multi-card contention.

### Enterprise Features
- ✅ **Asynchronous Processing** - Instant client response (~100ms); no need to wait for parsing to finish.
- ✅ **Task Persistence** - SQLite storage ensures no task loss on service restart.
- ✅ **Priority Queue** - Prioritize critical tasks.
- ✅ **Auto-Cleanup** - Regularly cleans up old result files while preserving database records.

### Intelligent Parsing
- ✅ **Dual Parsers** - PDF/images use VParse (GPU accelerated), Office/HTML, etc., use MarkItDown (Fast).
- ✅ **Content Retrieval** - API automatically returns Markdown content; supports image upload to MinIO.
- ✅ **RESTful API** - Supports any programming language integration.
- ✅ **Real-time Querying** - Check task progress and status at any time.

## 🏗️ System Architecture

```
Client Request → FastAPI Server (Instant task_id return)
                    ↓
              SQLite Task Queue (Concurrency Safe)
                    ↓
         LitServe Worker Pool (Active Polling + GPU Auto Load Balancing)
                    ↓
              VParse / MarkItDown Parsing
                    ↓
         Task Scheduler (Optional Monitoring Component)
```

**Architecture Characteristics**:
- ✅ **Worker Active Mode**: Workers continuously loop to pull tasks, no scheduler trigger required.
- ✅ **Concurrency Safe**: SQLite uses atomic operations to prevent duplicate task processing.
- ✅ **Auto Load Balancing**: LitServe automatically assigns tasks to idle GPUs.
- ✅ **Intelligent Parsing**: PDF/images use VParse, other formats use MarkItDown.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd projects/vparse_heavy
pip install -r requirements.txt
```

> **Supported File Formats**:
> - 📄 **PDF and Images** (.pdf, .png, .jpg, .jpeg, .bmp, .tiff, .webp) - Parsed with VParse (GPU accelerated)
> - 📊 **All Other Formats** (Office, HTML, Text, etc.) - Parsed with MarkItDown (Fast processing)
>   - Office: .docx, .doc, .xlsx, .xls, .pptx, .ppt
>   - Web: .html, .htm
>   - Text: .txt, .md, .csv, .json, .xml, etc.

### 2. Start Services

```bash
# Start all services with one click (recommended)
python start_all.py

# Or with custom configuration
python start_all.py --workers-per-device 2 --devices 0,1
```

> **Note for Windows Users**: Optimized for Windows multiprocessing; works out of the box.

### 3. Use the API

**Option A: Browser API Docs**
```
http://localhost:8000/docs
```

**Option B: Python Client**
```python
python client_example.py
```

**Option C: cURL Command**
```bash
# Submit a task
curl -X POST http://localhost:8000/api/v1/tasks/submit \
  -F "file=@document.pdf" \
  -F "lang=ch"

# Query status (returns content automatically on completion)
curl http://localhost:8000/api/v1/tasks/{task_id}

# Query status and upload images to MinIO
curl "http://localhost:8000/api/v1/tasks/{task_id}?upload_images=true"
```

## 📁 Project Structure

```
vparse_heavy/
├── task_db.py              # Database management (Concurrency safe, cleanup support)
├── api_server.py           # API Server (Auto content return)
├── litserve_worker.py      # Worker Pool (Active polling + Dual parsers)
├── task_scheduler.py       # Task scheduler (Optional monitoring)
├── start_all.py            # Startup script
├── client_example.py       # Client example
└── requirements.txt        # Dependency configuration
```

**Core Component Description**:
- `task_db.py`: Uses atomic operations to ensure concurrency safety, supports old task cleanup.
- `api_server.py`: Query interface automatically returns Markdown content, supports MinIO image upload.
- `litserve_worker.py`: Worker active loop polling for tasks, supports VParse and MarkItDown dual parsing.
- `task_scheduler.py`: Optional component, used only for monitoring and health checks (default 5-minute monitoring, 15-minute health check).


## 📚 Examples

### Example 1: Submit Task and Wait for Results (Auto-return)

```python
import requests
import time

# Submit document
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/tasks/submit',
        files={'file': f},
        data={'lang': 'ch', 'priority': 0}
    )
    task_id = response.json()['task_id']
    print(f"✅ Task submitted: {task_id}")

# Poll for completion
while True:
    response = requests.get(f'http://localhost:8000/api/v1/tasks/{task_id}')
    result = response.json()
    
    if result['status'] == 'completed':
        # v2.0 feature: Content is returned automatically
        if result.get('data'):
            content = result['data']['content']
            print(f"✅ Parsing complete, length: {len(content)} chars")
            print(f"   Parser: {result['data'].get('parser', 'Unknown')}")
            
            # Save result
            with open('output.md', 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            # Result files cleaned up
            print(f"⚠️  Task completed but files were cleaned up: {result.get('message', '')}")
        break
    elif result['status'] == 'failed':
        print(f"❌ Failed: {result['error_message']}")
        break
    
    print(f"⏳ Processing... status: {result['status']}")
    time.sleep(2)
```

### Example 2: Upload Images to MinIO (Optional)

```python
import requests

task_id = "your-task-id"

# v2.0: Returns content automatically, optionally uploads images to MinIO
response = requests.get(
    f'http://localhost:8000/api/v1/tasks/{task_id}',
    params={'upload_images': True}  # Enable image upload
)

result = response.json()
if result['status'] == 'completed' and result.get('data'):
    # Image links replaced with MinIO URLs (HTML <img> format)
    content = result['data']['content']
    images_uploaded = result['data']['images_uploaded']
    
    print(f"✅ Images uploaded to MinIO: {images_uploaded}")
    print(f"   Content length: {len(content)} chars")
    
    # Save Markdown with cloud image links
    with open('output_with_cloud_images.md', 'w', encoding='utf-8') as f:
        f.write(content)
```

### Example 3: Batch Processing

```python
import requests
import concurrent.futures

files = ['doc1.pdf', 'report.docx', 'data.xlsx']

def process_file(file_path):
    # Submit task
    with open(file_path, 'rb') as f:
        response = requests.post(
            'http://localhost:8000/api/v1/tasks/submit',
            files={'file': f}
        )
    return response.json()['task_id']

# Concurrent submission
with concurrent.futures.ThreadPoolExecutor() as executor:
    task_ids = list(executor.map(process_file, files))
    print(f"✅ Submitted {len(task_ids)} tasks")
```

## ⚙️ Configuration

### Startup Parameters

```bash
python start_all.py [options]

Options:
  --output-dir PATH                 Output directory (default: /tmp/mineru_tianshu_output)
  --api-port PORT                   API server port (default: 8000)
  --worker-port PORT                Worker server port (default: 9000)
  --accelerator TYPE                Accelerator: auto/cuda/cpu/mps (default: auto)
  --workers-per-device N            Workers per GPU (default: 1)
  --devices DEVICES                 Specific GPUs to use (default: auto, all GPUs)
  --poll-interval SECONDS           Worker poll interval (default: 0.5s)
  --enable-scheduler                Enable the optional task scheduler (default: False)
  --monitor-interval SECONDS        Scheduler monitor interval (default: 300s = 5m)
  --cleanup-old-files-days N        Days to keep result files (default: 7, 0=disable)
```

**New Features**:
- `--poll-interval`: Frequency of worker polling when idle; 0.5s for near-instant response.
- `--enable-scheduler`: Optional; used only for system health and monitoring.
- `--monitor-interval`: Logging frequency for scheduler; recommended 5-10m.
- `--cleanup-old-files-days`: Automatically purges old result files but keeps DB records.

### Hardware Requirements

| Backend | VRAM Requirement | Recommended Configuration |
| --- | --- | --- |
| pipeline | 6GB+ | RTX 2060 or higher |
| vlm-transformers | 8GB+ | RTX 3060 or higher |
| vlm-vllm-engine | 8GB+ | RTX 4070 or higher |

Options:
  --output-dir PATH                 Output directory (default: /tmp/vparse_heavy_output)
  --api-port PORT                   API port (default: 8000)
  --worker-port PORT                Worker port (default: 9000)
  --accelerator TYPE                Accelerator type: auto/cuda/cpu/mps (default: auto)
  --workers-per-device N            Workers per GPU (default: 1)
  --devices DEVICES                 GPU devices to use (default: auto, uses all GPUs)
  --poll-interval SECONDS           Worker task pull interval (default: 0.5s)
  --enable-scheduler                Enable optional task scheduler (default: off)
  --monitor-interval SECONDS        Scheduler monitor interval (default: 300s=5min)
  --cleanup-old-files-days N        Cleanup result files older than N days (default: 7 days, 0=disable)
```

> Full Docs: http://localhost:8000/docs

### 1. Submit Task
`POST /api/v1/tasks/submit`

Parameters:
- `file`: File (required)
- `backend`: pipeline | vlm-transformers | vlm-vllm-engine (default: pipeline)
- `lang`: ch | en | korean | japan | ... (default: ch)
- `priority`: 0-100 (higher is prioritized, default: 0)

### 2. Query Task
`GET /api/v1/tasks/{task_id}?upload_images=false`

Parameters:
- `upload_images`: Whether to upload to MinIO (default: false)

Returns:
- `status`: pending | processing | completed | failed
- `data`: **Automatically returned** upon completion
  - `markdown_file`: Filename
  - `content`: Full Markdown content
  - `images_uploaded`: Boolean
  - `has_images`: Boolean

### 3. Queue Statistics
`GET /api/v1/queue/stats`

Returns counts of tasks in each state.

## 🆕 Version Updates

### v2.0 Major Improvements

**1. Worker Auto-Polling Mode**
- ✅ Workers pull tasks in a loop; no scheduler trigger required.
- ✅ Default 0.5s interval for extreme responsiveness.
- ✅ Idle sleep avoids CPU waste.

**2. Concurrency Enhancements**
- ✅ Uses `BEGIN IMMEDIATE` for atomic database access.
- ✅ Prevents duplicate task processing.

**3. Optional Scheduler**
- ✅ No longer required; workers run independently.
- ✅ Reduces system overhead.

**4. Auto-Cleanup**
- ✅ Configurable retention period for result files (default 7 days).
- ✅ Preserves DB records for audit trails.

**5. multi-GPU Optimization**
- ✅ Fixed multi-card VRAM contention issues.
- ✅ Process isolation via `CUDA_VISIBLE_DEVICES`.

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

### 1. Submit Task
```http
POST /api/v1/tasks/submit

Parameters:
  file: File (Required)
  backend: pipeline | vlm-transformers | vlm-vllm-engine (Default: pipeline)
  lang: ch | en | korean | japan | ... (Default: ch)
  priority: 0-100 (Higher number = higher priority, Default: 0)
```

### 2. Query Task
```http
GET /api/v1/tasks/{task_id}?upload_images=false

Parameters:
  upload_images: Whether to upload images to MinIO (Default: false)

Returns:
  - status: pending | processing | completed | failed
  - data: **Auto-returns** Markdown content upon task completion
    - markdown_file: Filename
    - content: Full Markdown content
    - images_uploaded: Whether images were uploaded
    - has_images: Whether it contains images
  - message: Warning if result files have been cleaned up
  
Note:
  - v2.0 new feature: Completed tasks automatically return content, no extra request needed.
  - If result files have been cleaned (beyond retention period), `data` will be null but the task record remains queryable.
```

### 3. Queue Statistics
```http
GET /api/v1/queue/stats

Returns: Task count statistics for each status.
```

### 4. Cancel Task
```http
DELETE /api/v1/tasks/{task_id}

Can only cancel tasks in pending status.
```

### 5. Management Interfaces

**Reset Timed-out Tasks**
```http
POST /api/v1/admin/reset-stale?timeout_minutes=60

Resets timed-out processing tasks to pending.
```

**Cleanup Old Tasks**
```http
POST /api/v1/admin/cleanup?days=7

Manual trigger for old task cleanup (auto-cleanup runs every 24 hours).
```

## 🔧 Troubleshooting

### Problem 1: Worker Fails to Start

**Check GPU**
```bash
nvidia-smi  # Should display GPU info
```

**Check Dependencies**
```bash
pip list | grep -E "(vparse|litserve|torch)"
```

### Problem 2: Task Stays Pending

> ⚠️ **Important**: Workers are now in active polling mode and do not require scheduler triggers!

**Check if Worker is Running**
```bash
# Windows
tasklist | findstr python

# Linux/Mac
ps aux | grep litserve_worker
```

**Check Worker Health Status**
```bash
curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d '{"action":"health"}'
```

**Check Database Status**
```bash
python -c "from task_db import TaskDB; db = TaskDB(); print(db.get_queue_stats())"
```

### Problem 3: Out of Memory or Multi-GPU Contention

**Reduce Worker Count**
```bash
python start_all.py --workers-per-device 1
```

**Set VRAM limit**
```bash
export VPARSE_VIRTUAL_VRAM_SIZE=6
python start_all.py
```

**Specify Specific GPUs**
```bash
# Only use GPU 0
python start_all.py --devices 0
```

> 💡 **Tip**: The new version fixes multi-card VRAM contention issues. Each process only uses its assigned GPU by setting `CUDA_VISIBLE_DEVICES`.

### Problem 4: Port Already in Use

**Check Occupancy**
```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

**Use Other Ports**
```bash
python start_all.py --api-port 8080 --worker-port 9090
```

### Problem 5: Result Files Missing

**Query Task Status**
```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

**Description**: If it returns `result files have been cleaned up`, the files were deleted (default after 7 days).

**Solution**:
```bash
# Extend retention to 30 days
python start_all.py --cleanup-old-files-days 30

# or disable auto-cleanup
python start_all.py --cleanup-old-files-days 0
```

### Problem 6: Duplicate Task Processing

**Symptom**: The same task is processed by multiple workers.

**Cause**: Should not happen; database uses atomic operations to prevent duplicates.

**Troubleshooting**:
```bash
# Check if multiple TaskDB instances are connecting to different database files
# Ensure all components use the same vparse_heavy.db
```

## 🛠️ Technology Stack

- **Web**: FastAPI + Uvicorn
- **Parser**: VParse (PDF/Images) + MarkItDown (Office/Text/HTML, etc.)
- **GPU Scheduling**: LitServe (Auto load balancing)
- **Storage**: SQLite (Concurrency safe) + MinIO (Optional)
- **Logging**: Loguru
- **Concurrency Model**: Worker active polling + Atomic operations

## 🆕 Version Updates

### v2.0 Major Improvements

**1. Worker Active Polling Mode**
- ✅ Workers continuously loop to pull tasks, no scheduler trigger required.
- ✅ Default 0.5s polling interval for extremely fast response.
- ✅ Automatic sleep when idle, no CPU overhead.

**2. Enhanced Database Concurrency Safety**
- ✅ Uses `BEGIN IMMEDIATE` and atomic operations.
- ✅ Prevents duplicate task processing.
- ✅ Supports concurrent polling by multiple workers.

**3. Optional Scheduler**
- ✅ No longer a required component; workers can run independently.
- ✅ Used only for system monitoring and health checks.
- ✅ Off by default, reducing system overhead.

**4. Result File Cleanup Function**
- ✅ Automatically cleans old result files (default 7 days).
- ✅ Preserves database records for querying.
- ✅ Configurable cleanup cycle or disablement.

**5. API Auto-Return Content**
- ✅ Query interface automatically returns Markdown content.
- ✅ No extra request needed to retrieve results.
- ✅ Supports image upload to MinIO.

**6. Multi-GPU VRAM Optimization**
- ✅ Fixes multi-card VRAM occupancy issues.
- ✅ Each process only uses its assigned GPU.
- ✅ Isolation via `CUDA_VISIBLE_DEVICES`.

### Migration Guide (v1.x → v2.0)

**No code changes required**, just note:
1. Scheduler is now optional.
2. Result files cleaned after 7 days by default; use `--cleanup-old-files-days 0` to disable.
3. API query interface now returns `data` field with full content.

### Performance Gains

| Metric | v1.x | v2.0 | Gain |
|-----|------|------|-----|
| Task Response Latency<sup>※</sup> | 5-10s (Scheduler Polling) | 0.5s (Worker Active Polling) | **10-20x** |
| Concurrency Safety | Basic Lock Mechanism | Atomic Ops + Status Checks | **Reliability Improvement** |
| Multi-GPU Efficiency | Occasional VRAM Conflicts | Full Isolation, No Conflicts | **Stability Improvement** |
| System Overhead | Continuous Scheduler Run | Optional Monitoring (5 min) | **Resource Saving** |

※ Task response latency refers to the interval between task addition and when a Worker starts processing. v1.x was primarily limited by the scheduler polling interval, not end-to-end processing time. Actual end-to-end response time also includes task type and all system load factors.

## 📝 Core Dependencies

```txt
vparse[core]>=2.5.0      # VParse Core
fastapi>=0.115.0         # Web Framework
litserve>=0.2.0          # GPU Load Balancing
markitdown>=0.1.3        # Office Document Parsing
minio>=7.2.0             # MinIO Object Storage
```

## 🤝 Contribution

Issues and Pull Requests are welcome!

## 📄 License

Follows VParse main project license

---

**Heavy (Heavy)** - Enterprise-grade multi-GPU document parsing service ⚡️

*Named after the first star of the Big Dipper, symbolizing core scheduling capability*
