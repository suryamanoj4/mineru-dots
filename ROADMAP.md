# VParse OCR Toolkit — Development Roadmap

> **Vision**: One-stop, production-ready OCR toolkit with async-first inference, pluggable backends, optimized performance, deployable as Python library and Docker service.

**Current Version**: 1
**Status**: Active Development

---

## v1 — Async Inference & Library Foundation

**Theme**: Async-first inference, unified library API, pluggable backend architecture.

| Area | What |
|------|------|
| **Unified Public API** | `VParse` sync + `AsyncVParse` async classes with context manager support. `vparse/__init__.py` exports |
| **Configuration System** | Pydantic-based config with hierarchical merge (defaults < file < env < programmatic) |
| **Exception Hierarchy** | `VParseError` base with `BackendError`, `ModelLoadError`, `OCRProcessingError`, `ConfigurationError`, `TimeoutError` |
| **Type Hints & Stubs** | `py.typed` marker, full type annotations on all public APIs |
| **BackendProtocol** | Async-first protocol interface for all backends (doc_analyze, initialize, shutdown) |
| **BackendRegistry** | Pluggable backend discovery with register, get, list_available, auto_select |
| **Pipeline Async Support** | Convert pipeline and lite backends to async (remove the sync fallback that blocks the event loop) |
| **True Streaming Inference** | Async generator yielding pages as they complete. SSE endpoint in FastAPI. No double-pass |
| **Model Warmup** | Preload models and run dummy inference on server startup. /ready endpoint |
| **PyPI Packaging** | py.typed in package data, python -m build in CI |

---

## v2 — Performance & Memory Optimization

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

## v3 — KV Cache Optimization

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

## v4 — Bulk Processing & Job Management

**Theme**: High-throughput batch processing with queues, progress tracking, and resilience.

| Area | What |
|------|------|
| **Bulk Processing API** | BulkProcessor.submit, Job status/progress tracking, async iteration over results |
| **Redis/Celery Queue** | Celery workers, Redis broker, horizontal scaling, result backend |
| **Priority Queues** | Critical/high/normal/low tiers, separate queues per priority |
| **Progress & ETA** | Per-job progress events, throughput tracking, estimated completion time |
| **Checkpoint/Resume** | API-level checkpointing, resume interrupted bulk jobs from failure point |
| **Rate Limiting** | Throttle submission rate, backpressure when queue is full |

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
| v1 | Async Inference & Library Foundation | Async-first pipeline, unified API, streaming, warmup |
| v2 | Performance & Memory Optimization | Mixed precision, memory pooling, dynamic batching, OOM prevention |
| v3 | KV Cache Optimization | Prefix sharing, page similarity, cache tuning, metrics |
| v4 | Bulk Processing & Job Management | Queues, progress, checkpoint/resume, rate limiting |
| v5 | Multi-Model VLM & More Engines | Qwen2-VL, InternVL2, Nougat, Ollama, TGI, auto-selection |
| v6 | Output Formats, Docker & API Server | DOCX, searchable PDF, K8s, auth, multi-backend API |
| v7 | Testing, Monitoring & Docs | Coverage >85%, Prometheus, Grafana, tutorials |
