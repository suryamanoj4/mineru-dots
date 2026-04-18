# VParse Heavy (Heavy)

> Heavy - 企业级多GPU文档解析服务  
> 结合 SQLite 任务队列 + LitServe GPU负载均衡的最佳方案

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

### 智能解析
- ✅ **双解析器** - PDF/图片用 VParse(GPU加速), Office/HTML等用 MarkItDown(快速)
- ✅ **内容获取** - API自动返回 Markdown 内容,支持图片上传到 MinIO
- ✅ **RESTful API** - 支持任何编程语言接入
- ✅ **实时查询** - 随时查看任务进度和状态

## 🏗️ System Architecture

```
客户端请求 → FastAPI Server (立即返回 task_id)
                    ↓
              SQLite 任务队列 (并发安全)
                    ↓
         LitServe Worker Pool (主动拉取 + GPU自动负载均衡)
                    ↓
              VParse / MarkItDown 解析
                    ↓
         Task Scheduler (可选监控组件)
```

**架构特点**:
- ✅ **Worker 主动模式**: Workers 持续循环拉取任务,无需调度器触发
- ✅ **并发安全**: SQLite 使用原子操作防止任务重复处理
- ✅ **自动负载均衡**: LitServe 自动分配任务到空闲 GPU
- ✅ **智能解析**: PDF/图片用 VParse,其他格式用 MarkItDown

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd projects/vparse_heavy
pip install -r requirements.txt
```

> **支持的文件格式**:
> - 📄 **PDF 和图片** (.pdf, .png, .jpg, .jpeg, .bmp, .tiff, .webp) - 使用 VParse 解析（GPU 加速）
> - 📊 **其他所有格式** (Office、HTML、文本等) - 使用 MarkItDown 解析（快速处理）
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
├── task_db.py              # 数据库管理 (并发安全,支持清理)
├── api_server.py           # API 服务器 (自动返回内容)
├── litserve_worker.py      # Worker Pool (主动拉取 + 双解析器)
├── task_scheduler.py       # 任务调度器 (可选监控)
├── start_all.py            # 启动脚本
├── client_example.py       # 客户端示例
└── requirements.txt        # 依赖配置
```

**核心组件说明**:
- `task_db.py`: 使用原子操作保证并发安全,支持旧任务清理
- `api_server.py`: 查询接口自动返回Markdown内容,支持MinIO图片上传
- `litserve_worker.py`: Worker主动循环拉取任务,支持VParse和MarkItDown双解析
- `task_scheduler.py`: 可选组件,仅用于监控和健康检查(默认5分钟监控,15分钟健康检查)

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

选项:
  --output-dir PATH                 输出目录 (默认: /tmp/vparse_heavy_output)
  --api-port PORT                   API端口 (默认: 8000)
  --worker-port PORT                Worker端口 (默认: 9000)
  --accelerator TYPE                加速器类型: auto/cuda/cpu/mps (默认: auto)
  --workers-per-device N            每个GPU的worker数 (默认: 1)
  --devices DEVICES                 使用的GPU设备 (默认: auto，使用所有GPU)
  --poll-interval SECONDS           Worker拉取任务间隔 (默认: 0.5秒)
  --enable-scheduler                启用可选的任务调度器 (默认: 不启动)
  --monitor-interval SECONDS        调度器监控间隔 (默认: 300秒=5分钟)
  --cleanup-old-files-days N        清理N天前的结果文件 (默认: 7天, 0=禁用)
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

### 1. 提交任务
```http
POST /api/v1/tasks/submit

参数:
  file: 文件 (必需)
  backend: pipeline | vlm-transformers | vlm-vllm-engine (默认: pipeline)
  lang: ch | en | korean | japan | ... (默认: ch)
  priority: 0-100 (数字越大越优先，默认: 0)
```

### 2. 查询任务
```http
GET /api/v1/tasks/{task_id}?upload_images=false

参数:
  upload_images: 是否上传图片到 MinIO (默认: false)

返回:
  - status: pending | processing | completed | failed
  - data: 任务完成后**自动返回** Markdown 内容
    - markdown_file: 文件名
    - content: 完整的 Markdown 内容
    - images_uploaded: 是否已上传图片
    - has_images: 是否包含图片
  - message: 如果结果文件已清理会提示
  
注意:
  - v2.0 新特性: 完成的任务会自动返回内容,无需额外请求
  - 如果结果文件已被清理(超过保留期),data 为 null 但任务记录仍可查询
```

### 3. 队列统计
```http
GET /api/v1/queue/stats

返回: 各状态任务数量统计
```

### 4. 取消任务
```http
DELETE /api/v1/tasks/{task_id}

只能取消 pending 状态的任务
```

### 5. 管理接口

**重置超时任务**
```http
POST /api/v1/admin/reset-stale?timeout_minutes=60

将超时的 processing 任务重置为 pending
```

**清理旧任务**
```http
POST /api/v1/admin/cleanup?days=7

仅用于手动触发清理(自动清理会每24小时执行一次)
```

## 🔧 故障排查

### 问题1: Worker 无法启动

**检查GPU**
```bash
nvidia-smi  # 应显示GPU信息
```

**检查依赖**
```bash
pip list | grep -E "(vparse|litserve|torch)"
```

### 问题2: 任务一直 pending

> ⚠️ **重要**: Worker 现在是主动拉取模式,不需要调度器触发!

**检查 Worker 是否运行**
```bash
# Windows
tasklist | findstr python

# Linux/Mac
ps aux | grep litserve_worker
```

**检查 Worker 健康状态**
```bash
curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d '{"action":"health"}'
```

**查看数据库状态**
```bash
python -c "from task_db import TaskDB; db = TaskDB(); print(db.get_queue_stats())"
```

### 问题3: 显存不足或多卡占用

**减少worker数量**
```bash
python start_all.py --workers-per-device 1
```

**设置显存限制**
```bash
export VPARSE_VIRTUAL_VRAM_SIZE=6
python start_all.py
```

**指定特定GPU**
```bash
# 只使用GPU 0
python start_all.py --devices 0
```

> 💡 **提示**: 新版本已修复多卡显存占用问题,通过设置 `CUDA_VISIBLE_DEVICES` 确保每个进程只使用分配的GPU

### 问题4: 端口被占用

**查看占用**
```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

**使用其他端口**
```bash
python start_all.py --api-port 8080 --worker-port 9090
```

### 问题5: 结果文件丢失

**查询任务状态**
```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

**说明**: 如果返回 `result files have been cleaned up`,说明结果文件已被清理(默认7天后)

**解决方案**:
```bash
# 延长保留时间为30天
python start_all.py --cleanup-old-files-days 30

# 或禁用自动清理
python start_all.py --cleanup-old-files-days 0
```

### 问题6: 任务重复处理

**症状**: 同一个任务被多个 worker 处理

**原因**: 这不应该发生,数据库使用了原子操作防止重复

**排查**:
```bash
# 检查是否有多个 TaskDB 实例连接不同的数据库文件
# 确保所有组件使用同一个 vparse_heavy.db
```

## 🛠️ 技术栈

- **Web**: FastAPI + Uvicorn
- **解析器**: VParse (PDF/图片) + MarkItDown (Office/文本/HTML等)
- **GPU 调度**: LitServe (自动负载均衡)
- **存储**: SQLite (并发安全) + MinIO (可选)
- **日志**: Loguru
- **并发模型**: Worker主动拉取 + 原子操作

## 🆕 版本更新说明

### v2.0 重大改进

**1. Worker 主动拉取模式**
- ✅ Workers 持续循环拉取任务,无需调度器触发
- ✅ 默认 0.5 秒拉取间隔,响应速度极快
- ✅ 空闲时自动休眠,不占用CPU资源

**2. 数据库并发安全增强**
- ✅ 使用 `BEGIN IMMEDIATE` 和原子操作
- ✅ 防止任务重复处理
- ✅ 支持多 Worker 并发拉取

**3. 调度器变为可选**
- ✅ 不再是必需组件,Workers 可独立运行
- ✅ 仅用于系统监控和健康检查
- ✅ 默认不启动,减少系统开销

**4. 结果文件清理功能**
- ✅ 自动清理旧结果文件(默认7天)
- ✅ 保留数据库记录供查询
- ✅ 可配置清理周期或禁用

**5. API 自动返回内容**
- ✅ 查询接口自动返回 Markdown 内容
- ✅ 无需额外请求获取结果
- ✅ 支持图片上传到 MinIO

**6. 多GPU显存优化**
- ✅ 修复多卡显存占用问题
- ✅ 每个进程只使用分配的GPU
- ✅ 通过 `CUDA_VISIBLE_DEVICES` 隔离

### 迁移指南 (v1.x → v2.0)

**无需修改代码**,只需注意:
1. 调度器现在是可选的,不启动也能正常工作
2. 结果文件默认7天后清理,如需保留请设置 `--cleanup-old-files-days 0`
3. API 查询接口现在会返回 `data` 字段包含完整内容

### 性能提升

| 指标 | v1.x | v2.0 | 提升 |
|-----|------|------|-----|
| 任务响应延迟<sup>※</sup> | 5-10秒 (调度器轮询) | 0.5秒 (Worker主动拉取) | **10-20倍** |
| 并发安全性 | 基础锁机制 | 原子操作 + 状态检查 | **可靠性提升** |
| 多GPU效率 | 有时会出现显存冲突 | 完全隔离,无冲突 | **稳定性提升** |
| 系统开销 | 调度器持续运行 | 可选监控(5分钟) | **资源节省** |

※ 任务响应延迟指任务添加到被 Worker 开始处理的时间间隔。v1.x 主要受调度器轮询间隔影响，非测量端到端处理时间。实际端到端响应时间还包括任务类型和系统负载所有因子。

## 📝 核心依赖

```txt
vparse[core]>=2.5.0      # VParse 核心
fastapi>=0.115.0         # Web 框架
litserve>=0.2.0          # GPU 负载均衡
markitdown>=0.1.3        # Office 文档解析
minio>=7.2.0             # MinIO 对象存储
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

遵循 VParse 主项目许可证

---

**Heavy (Heavy)** - 企业级多 GPU 文档解析服务 ⚡️

*北斗第一星，寓意核心调度能力*
