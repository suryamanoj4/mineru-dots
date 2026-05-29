# VParse OCR Toolkit — Development Roadmap

> **Vision**: One-stop, production-ready OCR toolkit with async-first inference, pluggable backends, optimized performance, deployable as Python library and Docker service.

**Current Version**: 1
**Status**: Active Development

---

## v1 — Async Inference & Mode Consolidation

**Theme**: Slim down 15 fragmented modes to 5, async-first VLM/Remote, unified library API, pluggable backends.

### Mode Consolidation

**Before (15 modes)**: `pipeline`, `lite`, `vlm-auto-engine`, `vlm-transformers`, `vlm-vllm-engine`, `vlm-vllm-async-engine`, `vlm-lmdeploy-engine`, `vlm-mlx-engine`, `vlm-http-client`, `vlm-dots-ocr-hf`, `vlm-dots-ocr-vllm`, `hybrid-auto-engine`, `hybrid-vllm-engine`, `hybrid-lmdeploy-engine`, `hybrid-http-client`

**After (5 modes)**:

| Mode | Execution | What |
|------|-----------|------|
| `pipeline` | sync | Layout detection + PaddleOCR/Tesseract + table/formula extraction |
| `lite` | sync | Tesseract-only, CPU fast path |
| `vlm` | **always async** | VLM with auto-optimized engine: vLLM (CUDA, default) → MLX (Apple Silicon) → LMDeploy (if `vlm-lmdeploy` explicitly) |
| `hybrid` | sync | VLM for layout + pipeline for dense OCR |
| `remote` | **always async** | HTTP client for any OpenAI-compatible server. User provides URL |

### What's Removed

- **All engine permutations removed** — no `vllm-engine` / `vllm-async-engine` / `transformers` / `lmdeploy-engine` / `mlx-engine` / `http-client` variants. The system autodetects the optimal engine for the hardware
- **Sync/async split removed from mode strings** — execution context (`VParse` vs `AsyncVParse`) determines sync vs async, not the mode name. vLLM `AsyncLLM` is always used (no performance penalty vs sync)
- **Hybrid engine variants removed** — hybrid always auto-selects the best VLM engine internally
- **`dots-ocr-*` variants removed** — dots.mocr is the only VLM model, no need to encode it in mode names

### Backend Auto-Selection

```
vlm:
  CUDA + vLLM available → AsyncLLM (in-process)  
  Apple Silicon + MLX  → asyncio.to_thread(mlx_vlm.predict)
  LMDeploy specified    → VLAsyncEngine (in-process)
  
remote:
  User provides URL     → httpx client, always async
  
hybrid:
  VLM engine autodetected same as vlm mode above
  Pipeline OCR always runs locally
```

### Deliverables

| Area | What |
|------|------|
| **Mode Slimming** | Remove all engine variants, consolidate dispatch, ensure backward compat aliases |
| **BackendProtocol** | Async-first interface for all 5 modes (doc_analyze, initialize, shutdown) |
| **BackendRegistry** | Register 5 backends, auto-select engine for vlm/hybrid based on hardware |
| **Unified Public API** | `VParse` and `AsyncVParse` classes. `AsyncVParse` auto-selects async-native engines |
| **Configuration System** | Pydantic-based config with hierarchical merge (defaults < file < env < programmatic) |
| **Exception Hierarchy** | `VParseError` base with `BackendError`, `ModelLoadError`, `OCRProcessingError`, `ConfigurationError`, `TimeoutError` |
| **Type Hints & Stubs** | `py.typed` marker, full type annotations on all public APIs |
| **True Streaming** | Async generator yielding pages as they complete. SSE endpoint. No double-pass |
| **Model Warmup** | Preload models on startup, dummy inference to warm GPU caches. /ready endpoint |
| **PyPI Packaging** | py.typed in package data, python -m build in CI |

---

## v2 — Bulk Processing & Job Management

**Theme**: High-throughput batch processing with queues, progress tracking, and resilience.

| Area | What |
|------|------|
| **Bulk Processing API** | BulkProcessor.submit, Job status/progress tracking, async iteration over results. Batch pages across books to amortize overhead |
| **Redis/Celery Queue** | Celery workers, Redis broker, horizontal scaling, result backend |
| **Priority Queues** | Critical/high/normal/low tiers, separate queues per priority |
| **Progress & ETA** | Per-job progress events, throughput tracking, estimated completion time |
| **Checkpoint/Resume** | API-level checkpointing, resume interrupted bulk jobs from failure point |
| **Rate Limiting** | Throttle submission rate, backpressure when queue is full |

---

## v3 — Performance & Memory Optimization

**Theme**: Reduce memory footprint, prevent OOM, speed up inference with mixed precision.

| Area | What |
|------|------|
| **Mixed Precision** | Configurable fp16/bf16/fp32 via VPARSE_INFERENCE_DTYPE. amp.autocast in pipeline inference |
| **Memory Pool** | Pre-allocated buffer pool for image tensors. Reuse padded arrays across batches |
| **Dynamic Batch Sizing** | Real-time VRAM monitoring, adjust batch size mid-processing based on memory pressure |
| **OOM Prevention** | Catch OutOfMemoryError, halve batch and retry, fall back to single-page if needed |
| **Model Lifecycle** | TTL-based auto-unload, LRU eviction from singleton cache, explicit shutdown on all backends |
| **GC Tuning** | Disable GC during inference, force collect between batch stages |
| **Memory Profiler** | CLI command showing per-component memory usage |

---

## v4 — KV Cache Optimization

**Theme**: Reduce redundant VLM computation through KV cache sharing and tuning.

| Area | What |
|------|------|
| **KV Cache Tuning** | Auto-calculate block_size, num_gpu_blocks, enable prefix_caching, tune max_num_batched_tokens for OCR |
| **Prefix Sharing** | Compute layout_hash per page, share KV cache prefix across pages with identical layout |
| **Page Similarity** | Group pages by layout/content similarity before bulk inference to maximize cache reuse |
| **Cache Eviction** | Configurable LRU/LFU/priority-based eviction policies |
| **Cache Metrics** | Hit/miss ratio, utilization, fragmentation, eviction rate, Prometheus export |
| **Batch-Aware Management** | Allocate/release cache per batch, overlap cache load with inference |

---

## v5 — Multi-Model VLM & More Engines

**Theme**: Support multiple VLM models and inference engines with auto-selection.

| Area | What |
|------|------|
| **Qwen2-VL** | 2B/7B/72B variants, strong multilingual support |
| **InternVL2/2.5** | 2B/8B/26B/76B, strong table and formula understanding |
| **Got-OCR2.0** | Specialized for OCR, high accuracy on printed text |
| **Nougat** | Scientific papers, native LaTeX output |
| **Ollama Engine** | Easy local deployment via Ollama API |
| **TGI Engine** | HuggingFace Text Generation Inference for enterprise |
| **Model Auto-Selection** | Auto-pick best model based on doc type, language, VRAM, content features |
| **Engine Auto-Detection** | Auto-pick best engine based on device, model, available dependencies |

---

## v6 — Output Formats, Docker & API Server

**Theme**: Production deployment with rich output formats and secure API.

| Area | What |
|------|------|
| **DOCX Export** | Preserve styles, images, tables in Word format |
| **Searchable PDF** | OCR text as invisible layer over original PDF |
| **EPUB Export** | E-book reader compatible output |
| **LaTeX Export** | Full LaTeX document with sections, tables, formulas |
| **RAG-Ready Chunks** | Semantic chunking with embeddings and metadata |
| **Multi-Backend API** | Dedicated endpoints per backend |
| **Authentication** | API key + JWT support |
| **Rate Limiting** | Token bucket per API key |
| **Kubernetes Manifests** | Deployment, HPA, Service, Ingress, PVC |
| **Multi-Stage Dockerfile** | Build stage, runtime stage, CPU-only variant, slim variant |

---

## v7 — Testing, Monitoring & Docs

**Theme**: Quality, observability, and developer experience.

| Area | What |
|------|------|
| **Unit Tests >85%** | Mock external deps, test all modules, pytest-cov enforcement |
| **Integration Tests** | FastAPI endpoints, all backend combinations |
| **Load Tests** | Locust scripts for concurrent/sustained/spike loads |
| **Memory Leak Tests** | 1000+ request run with tracemalloc detection |
| **Benchmark Suite** | Compare all backends, engines, models; export to CSV/HTML |
| **Prometheus Metrics** | Request count, latency, pages processed, queue depth |
| **Grafana Dashboards** | Overview, backend performance, resource usage, cost/page |
| **Audit Logging** | Immutable request log with user, timestamp, parameters |
| **API Reference** | Auto-generated from docstrings |
| **Tutorials & Cookbook** | Jupyter notebooks, copy-paste recipes for common use cases |

---

## Version Summary

| Version | Theme | Focus |
|---------|-------|-------|
| v1 | Async Inference & Mode Consolidation | 15 → 5 modes, async-first VLM/Remote, unified API, streaming |
| v2 | Bulk Processing & Job Management | Batch API, queues, progress, checkpoint/resume |
| v3 | Performance & Memory Optimization | Mixed precision, memory pooling, dynamic batching, OOM prevention |
| v4 | KV Cache Optimization | Prefix sharing, page similarity, cache tuning, metrics |
| v5 | Multi-Model VLM & More Engines | Qwen2-VL, InternVL2, Nougat, Ollama, TGI, auto-selection |
| v6 | Output Formats, Docker & API Server | DOCX, searchable PDF, K8s, auth, multi-backend API |
| v7 | Testing, Monitoring & Docs | Coverage >85%, Prometheus, Grafana, tutorials |
