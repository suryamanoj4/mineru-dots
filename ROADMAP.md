# MinerU OCR Toolkit - Comprehensive Development Roadmap

> **Vision**: Transform MinerU into a one-stop, production-ready OCR toolkit with multiple backend support, optimized performance, and deployable as both a Python library and Docker service.

**Last Updated**: April 8, 2026  
**Current Version**: 2.7.6  
**Status**: Active Development

---

## Table of Contents

- [Module Status Overview](#module-status-overview)
- [Module 1-8: Detailed Implementation Guides](#detailed-module-guides)
  - [Module 1: Core Library & API Foundation](#module-1-core-library--api-foundation)
  - [Module 2: Backend Engine Abstraction Layer](#module-2-backend-engine-abstraction-layer)
  - [Module 3: Pipeline Backend Enhancements](#module-3-pipeline-backend-enhancements)
  - [Module 4: Multi-Model VLM Backend](#module-4-multi-model-vlm-backend)
  - [Module 5: Inference Engine Integration](#module-5-inference-engine-integration)
  - [Module 6: Memory & Performance Optimization](#module-6-memory--performance-optimization)
  - [Module 7: KV Cache Optimization System](#module-7-kv-cache-optimization-system)
  - [Module 8: Bulk Processing & Job Management](#module-8-bulk-processing--job-management)
- [Module 9-15: Detailed Implementation Guides](#detailed-module-guides-continued)
  - [Module 9: Docker & Deployment Services](#module-9-docker--deployment-services)
  - [Module 10: API Server Features](#module-10-api-server-features)
  - [Module 11: Document Processing Pipeline](#module-11-document-processing-pipeline)
  - [Module 12: Output Formats & Export](#module-12-output-formats--export)
  - [Module 13: Testing & Quality Assurance](#module-13-testing--quality-assurance)
  - [Module 14: Monitoring & Observability](#module-14-monitoring--observability)
  - [Module 15: Developer Experience & Documentation](#module-15-developer-experience--documentation)
- [Recommended Implementation Order](#recommended-implementation-order)
- [Getting Started](#getting-started)

---

## Module Status Overview

| Module | Title | Total Tasks | Implemented | Partial | Not Started | Completion % |
|--------|-------|-------------|-------------|---------|-------------|--------------|
| **M1** | Core Library & API Foundation | 8 | 2 | 2 | 4 | 37.5% |
| **M2** | Backend Engine Abstraction Layer | 8 | 0 | 1 | 7 | 6.25% |
| **M3** | Pipeline Backend Enhancements | 8 | 3 | 1 | 4 | 43.75% |
| **M4** | Multi-Model VLM Backend | 11 | 1 | 2 | 8 | 18.2% |
| **M5** | Inference Engine Integration | 9 | 3 | 2 | 4 | 44.4% |
| **M6** | Memory & Performance Optimization | 11 | 2 | 2 | 7 | 27.3% |
| **M7** | KV Cache Optimization System | 11 | 0 | 0 | 11 | 0% |
| **M8** | Bulk Processing & Job Management | 11 | 1 | 1 | 9 | 13.6% |
| **M9** | Docker & Deployment Services | 11 | 4 | 2 | 5 | 45.5% |
| **M10** | API Server Features | 10 | 2 | 2 | 6 | 30% |
| **M11** | Document Processing Pipeline | 11 | 3 | 1 | 7 | 31.8% |
| **M12** | Output Formats & Export | 11 | 3 | 1 | 7 | 31.8% |
| **M13** | Testing & Quality Assurance | 10 | 2 | 1 | 7 | 25% |
| **M14** | Monitoring & Observability | 9 | 0 | 1 | 8 | 5.6% |
| **M15** | Developer Experience & Documentation | 10 | 3 | 1 | 6 | 35% |
| **TOTAL** | | **148** | **29** | **19** | **100** | **25%** |

### Legend
- ✅ **IMPLEMENTED**: Feature exists and is functional
- ⚠️ **PARTIAL**: Feature exists but is incomplete or needs improvement
- ❌ **NOT IMPLEMENTED**: Feature does not exist
- 📋 **PLANNED**: Feature is mentioned in config/docs but not coded

---

## Detailed Module Guides

---

### Module 1: Core Library & API Foundation

**Goal**: Create a clean, importable Python library interface with unified API, proper configuration, type hints, and PyPI-ready packaging.

**Current Status**: 37.5% Complete (2 implemented, 2 partial, 4 not started)

#### Task Breakdown

##### 1.1 Design and implement unified public API
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: `mineru/__init__.py` is empty (only copyright comment). Users must use CLI commands (`mineru`, `mineru-api`) or call internal functions (`do_parse`, `aio_do_parse` from `mineru/cli/common.py`).
- **What to Build**:
  ```python
  # Desired API
  from mineru import MinerU
  
  # Simple usage
  ocr = MinerU(backend="pipeline", lang="en")
  result = ocr.process("document.pdf")
  
  # Context manager
  with MinerU(backend="vlm") as ocr:
      result = ocr.process("document.pdf")
  
  # Async support
  async with AsyncMinerU(backend="hybrid") as ocr:
      result = await ocr.process("document.pdf")
  ```
- **Files to Create/Modify**:
  - `mineru/__init__.py` - Export public API
  - `mineru/client.py` - New high-level MinerU class
  - `mineru/async_client.py` - Async version
- **Priority**: 🔴 CRITICAL - Foundation for all library usage

##### 1.2 Create high-level OCR class with context manager support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No unified class exists. Processing logic is scattered across `mineru/cli/common.py` (`do_parse`, `aio_do_parse`, `read_fn`).
- **What to Build**:
  - `MinerU` class with `__enter__`/`__exit__` for context manager
  - Constructor accepts: `backend`, `lang`, `device`, `config`, `output_format`
  - Methods: `process()`, `process_batch()`, `get_supported_backends()`, `get_version()`
  - Automatic resource cleanup (model unloading, memory release) on exit
- **Files to Create**:
  - `mineru/client.py` - Sync client
  - `mineru/async_client.py` - Async client
- **Priority**: 🔴 CRITICAL

##### 1.3 Implement configuration system
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `mineru/utils/config_reader.py` - Reads `~/.mineru.json` config file
  - `mineru/utils/os_env_config.py` - Reads environment variables
  - `mineru.template.json` - Template config with bucket_info, latex-delimiter, llm-aided, models-dir
  - **Gaps**: No programmatic config builder, no validation schema, no merge strategy (env → file → defaults), no runtime config changes
- **What to Build**:
  ```python
  from mineru import Config
  
  config = (
      Config()
      .set_backend("pipeline")
      .set_device("cuda")
      .set_language("en")
      .enable_formula()
      .enable_tables()
      .set_batch_size(8)
      .load_from_file("~/.mineru.json")  # Override with file
      .load_from_env()  # Override with env vars
  )
  ```
  - Pydantic-based config models with validation
  - Hierarchical config: defaults < file < env < programmatic
  - Runtime config updates without restart
- **Files to Modify**:
  - `mineru/utils/config_reader.py` - Add Pydantic models
  - `mineru/data/utils/schemas.py` - Extend with full config schema
- **Priority**: 🟡 HIGH

##### 1.4 Add custom exception hierarchy
- **Status**: ⚠️ PARTIAL
- **Current State**: Exceptions are scattered:
  - `mineru/data/utils/exceptions.py` - `FileNotExisted`, `InvalidConfig`, `InvalidParams`, `EmptyData`, `CUDA_NOT_AVAILABLE`
  - `mineru/model/table/rec/slanet_plus/table_structure_utils.py` - `ONNXRuntimeError`
  - `mineru/model/table/rec/unet_table/utils.py` - `ONNXRuntimeError`, `LoadImageError`
  - **Gaps**: No base `MinerUError` class, no hierarchy, not exported from `mineru/__init__.py`, missing critical exceptions (ModelLoadError, BackendError, OCRProcessingError, TimeoutError)
- **What to Build**:
  ```python
  class MinerUError(Exception):
      """Base exception for all MinerU errors"""
      pass
  
  class BackendError(MinerUError):
      """Backend-related errors"""
      pass
  
  class ModelLoadError(BackendError):
      """Failed to load model"""
      pass
  
  class OCRProcessingError(MinerUError):
      """Error during OCR processing"""
      pass
  
  class ConfigurationError(MinerUError):
      """Invalid configuration"""
      pass
  
  class InputError(MinerUError):
      """Invalid input (file not found, unsupported format, etc.)"""
      pass
  
  class TimeoutError(MinerUError):
      """Processing timeout"""
      pass
  ```
- **Files to Create/Modify**:
  - `mineru/exceptions.py` - New file with complete hierarchy
  - `mineru/__init__.py` - Export all exceptions
- **Priority**: 🟡 HIGH

##### 1.5 Create type hints and stubs for all public APIs
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: 
  - No `py.typed` marker file exists
  - Some internal modules use `typing` annotations (35 files), but public APIs are untyped
  - **Impact**: No IDE autocomplete, no mypy/Pyright type checking for library users
- **What to Build**:
  - Add `py.typed` empty file to `mineru/` package root
  - Add type hints to all public API functions/classes
  - Create `mineru/py.typed` marker file
  - Update `pyproject.toml` to include `py.typed` in package data
  - Run `mypy --strict` on public API surface
- **Files to Create/Modify**:
  - `mineru/py.typed` - New marker file
  - `mineru/__init__.py` - Add type hints to exports
  - `pyproject.toml` - Add `include_package_data = true`
- **Priority**: 🟡 HIGH

##### 1.6 Implement output format handlers
- **Status**: ✅ IMPLEMENTED (needs enhancement)
- **Current State**:
  - `mineru/utils/format_utils.py` - OTSL-to-HTML conversion, table cell/grid models (Pydantic)
  - `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py` - `union_make()` for MM_MD, NLP_MD, CONTENT_LIST
  - `mineru/backend/vlm/vlm_middle_json_mkcontent.py` - VLM union_make
  - `mineru/utils/enum_class.py` - `MakeMode` enum (MM_MD, NLP_MD, CONTENT_LIST, CONTENT_LIST_V2)
  - **Gaps**: No DOCX, EPUB, searchable PDF, CSV/TSV, LaTeX export. HTML converter is basic.
- **What to Build**: (See Module 12 for full details)
- **Priority**: 🟢 MEDIUM

##### 1.7 Add input source abstractions
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/data/data_reader_writer/base.py` - Abstract `DataReader`, `DataWriter` classes
  - `mineru/data/data_reader_writer/filebase.py` - `FileBasedDataReader`, `FileBasedDataWriter`
  - `mineru/data/data_reader_writer/s3.py` - S3 reader/writer
  - `mineru/data/data_reader_writer/multi_bucket_s3.py` - Multi-bucket S3
  - `mineru/data/io.py` - `IOReader`, `IOWriter`, `HttpReader`, `HttpWriter`, `S3Reader`, `S3Writer`
  - **Gaps**: No PIL Image input, no URL input, no bytes stream input, no PDF page iterator
- **What to Build**: (Enhance existing abstractions)
  - `ImageReader` - PIL Image, numpy array input
  - `URLReader` - HTTP/HTTPS URL input
  - `BytesReader` - In-memory bytes
  - `PDFPageIterator` - Stream pages one at a time
- **Priority**: 🟢 MEDIUM

##### 1.8 Package for PyPI distribution
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `pyproject.toml` has proper `[build-system]`, `[project]` metadata
  - Entry points: `mineru`, `mineru-vllm-server`, `mineru-lmdeploy-server`, `mineru-openai-server`, `mineru-models-download`, `mineru-api`, `mineru-gradio`
  - Optional dependency groups: `test`, `dev`, `vlm`, `vllm`, `lmdeploy`, `mlx`, `pipeline`, `api`, `gradio`, `core`, `all`
  - Python `>=3.10,<3.14`
  - **Gaps**: No `py.typed` marker, no `long_description_content_type`, missing some package data (resources, models), CI/CD only builds on `*released` tag
- **What to Build**:
  - Add `py.typed` to package data
  - Add `[tool.setuptools.package-data]` to include resources, templates
  - Add classifiers for intended use cases
  - Test `pip install mineru` in clean environment
  - Add `python -m build` to CI workflow
- **Files to Modify**:
  - `pyproject.toml` - Add package data, classifiers
  - `.github/workflows/python-package.yml` - Already exists, enhance for PyPI
- **Priority**: 🟡 HIGH

---

### Module 2: Backend Engine Abstraction Layer

**Goal**: Create a pluggable backend system with interface contracts, dynamic discovery, fallback chains, health monitoring, and lifecycle management.

**Current Status**: 6.25% Complete (0 implemented, 1 partial, 7 not started)

#### Task Breakdown

##### 2.1 Design BackendProtocol interface
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Backends are separate modules with hardcoded `doc_analyze()` functions. Selection logic is a string-based `if/elif` chain in `mineru/cli/common.py` lines 297-350:
  ```python
  if backend == "pipeline":
      _process_pipeline(...)
  elif backend.startswith("vlm-"):
      _process_vlm(...)
  elif backend.startswith("hybrid-"):
      _process_hybrid(...)
  ```
- **What to Build**:
  ```python
  from abc import ABC, abstractmethod
  from typing import Protocol, runtime_checkable
  from mineru.data.data_reader_writer import DataWriter
  
  @runtime_checkable
  class BackendProtocol(Protocol):
      """Protocol that all OCR backends must implement"""
      
      @abstractmethod
      async def doc_analyze(
          self,
          pdf_bytes: bytes,
          lang: str,
          parse_method: str = "auto",
          image_writer: DataWriter | None = None,
          **kwargs
      ) -> tuple[dict, dict]:
          """Analyze document and return (middle_json, model_output)"""
          ...
      
      @abstractmethod
      def get_backend_name(self) -> str:
          """Return unique backend identifier"""
          ...
      
      @abstractmethod
      def get_supported_languages(self) -> list[str]:
          """Return list of supported language codes"""
          ...
      
      @abstractmethod
      def is_available(self) -> bool:
          """Check if backend is ready (models loaded, dependencies met)"""
          ...
      
      @abstractmethod
      async def initialize(self) -> None:
          """Load models and prepare for inference"""
          ...
      
      @abstractmethod
      async def shutdown(self) -> None:
          """Unload models and release resources"""
          ...
  ```
- **Files to Create**:
  - `mineru/backend/base.py` - BackendProtocol, BaseBackend ABC
- **Priority**: 🔴 CRITICAL - Foundation for pluggable backends

##### 2.2 Implement BackendRegistry
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No registry. Backend choices are hardcoded strings.
- **What to Build**:
  ```python
  class BackendRegistry:
      """Dynamic backend discovery and selection"""
      
      _backends: dict[str, type[BackendProtocol]] = {}
      
      @classmethod
      def register(cls, name: str, backend_class: type[BackendProtocol]):
          """Register a backend class with unique name"""
          cls._backends[name] = backend_class
      
      @classmethod
      def get(cls, name: str) -> BackendProtocol:
          """Get backend instance by name"""
          ...
      
      @classmethod
      def list_available(cls) -> dict[str, dict]:
          """List all registered backends with metadata"""
          return {
              name: {
                  "available": backend.is_available(),
                  "languages": backend.get_supported_languages(),
                  "device": backend.get_device(),
              }
              for name, backend in cls._backends.items()
          }
      
      @classmethod
      def auto_select(
          cls,
          doc_type: str | None = None,
          lang: str | None = None,
          device: str | None = None,
      ) -> str:
          """Auto-select best backend for given constraints"""
          ...
  ```
- **Files to Create**:
  - `mineru/backend/registry.py` - BackendRegistry implementation
  - `mineru/backend/__init__.py` - Register built-in backends
- **Priority**: 🔴 CRITICAL

##### 2.3 Create backend configuration schema
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No backend-specific config schema. Settings are passed as kwargs or env vars.
- **What to Build**:
  ```yaml
  # mineru-backends.yaml
  backends:
    pipeline:
      ocr_engine: "paddle"  # or "tesseract", "easyocr", "rapidocr"
      layout_model: "doclayout_yolo"
      formula_enable: true
      table_enable: true
      batch_size: 8
      device: "cuda"
    
    vlm:
      model: "dots.mocr"
      engine: "vllm"
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.5
      max_model_len: 8192
    
    hybrid:
      vlm_model: "dots.mocr"
      pipeline_ocr: "paddle"
      batch_ratio: 0.5
  ```
  - Pydantic schema validation on load
  - Schema versioning for backward compatibility
- **Files to Create**:
  - `mineru/backend/config_schema.py` - Pydantic models
  - `mineru/backends.example.yaml` - Example config
- **Priority**: 🟡 HIGH

##### 2.4 Implement backend fallback chains
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No fallback. If backend fails, exception is raised.
- **What to Build**:
  ```python
  class FallbackChain:
      """Execute backends in order until success"""
      
      def __init__(self, backend_names: list[str]):
          self.backends = backend_names
      
      async def execute(self, pdf_bytes: bytes, **kwargs) -> dict:
          errors = []
          for backend_name in self.backends:
              try:
                  backend = BackendRegistry.get(backend_name)
                  return await backend.doc_analyze(pdf_bytes, **kwargs)
              except Exception as e:
                  errors.append((backend_name, str(e)))
                  logger.warning(f"Backend {backend_name} failed: {e}")
          raise FallbackChainError(
              f"All backends failed: {errors}"
          )
  
  # Usage
  chain = FallbackChain(["vlm", "hybrid", "pipeline"])
  result = await chain.execute(pdf_bytes)
  ```
- **Files to Create**:
  - `mineru/backend/fallback.py` - FallbackChain implementation
- **Priority**: 🟡 HIGH

##### 2.5 Add backend performance profiling utilities
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Only basic `logger.debug()` timing in pipeline code.
- **What to Build**:
  - `BackendProfiler` context manager to track:
    - Model load time
    - Inference latency (per page, per batch)
    - Memory usage (before/after)
    - Throughput (pages/sec)
  - `benchmark()` function to run standardized test suite
  - Export results to JSON/CSV
- **Files to Create**:
  - `mineru/backend/profiler.py`
- **Priority**: 🟢 MEDIUM

##### 2.6 Create backend health monitoring and circuit breaker
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No health checks.
- **What to Build**:
  ```python
  from enum import Enum
  
  class HealthStatus(Enum):
      HEALTHY = "healthy"
      DEGRADED = "degraded"
      UNHEALTHY = "unhealthy"
  
  class CircuitBreaker:
      """Prevent cascading failures"""
      
      def __init__(
          self,
          failure_threshold: int = 5,
          recovery_timeout: float = 60.0,
      ):
          self.failure_count = 0
          self.state = "closed"  # closed, open, half-open
          ...
      
      def record_success(self):
          self.failure_count = 0
          self.state = "closed"
      
      def record_failure(self):
          self.failure_count += 1
          if self.failure_count >= self.failure_threshold:
              self.state = "open"
  ```
- **Files to Create**:
  - `mineru/backend/health.py` - Health monitoring
  - `mineru/backend/circuit_breaker.py` - Circuit breaker pattern
- **Priority**: 🟢 MEDIUM

##### 2.7 Implement backend warmup and preloading
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Only implicit lazy loading via singletons.
- **What to Build**:
  ```python
  class BackendWarmer:
      """Preload models to avoid cold start latency"""
      
      def __init__(self, registry: BackendRegistry):
          self.registry = registry
      
      async def warmup(self, backend_names: list[str]):
          """Load models for specified backends"""
          for name in backend_names:
              backend = self.registry.get(name)
              await backend.initialize()
              # Run dummy inference to warm up GPU caches
              await backend.doc_analyze(
                  self._get_sample_pdf(), lang="en"
              )
  ```
- **Files to Create**:
  - `mineru/backend/warmup.py`
- **Priority**: 🟢 MEDIUM

##### 2.8 Add backend lifecycle management
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - **init/load**: Implicit via singletons (`ModelSingleton`, `AtomModelSingleton`, `HybridModelSingleton`)
  - **unload**: NOT IMPLEMENTED. `clean_memory(device)` in `mineru/utils/model_utils.py` does `gc.collect()` + `torch.cuda.empty_cache()`, but models stay in memory
- **What to Build**:
  - Explicit `unload()`, `dispose()`, `shutdown()` methods
  - Reference counting for shared models
  - Automatic unload when backend not used for N seconds
  - `BackendLifecycleManager` to coordinate across backends
- **Files to Create/Modify**:
  - `mineru/backend/lifecycle.py` - Lifecycle manager
  - `mineru/utils/model_utils.py` - Add model unload utilities
- **Priority**: 🟡 HIGH

---

### Module 3: Pipeline Backend Enhancements

**Goal**: Expand pipeline backend with multiple OCR engines (Tesseract, EasyOCR, RapidOCR), optimizations, and pipeline-lite mode.

**Current Status**: 43.75% Complete (3 implemented, 1 partial, 4 not started)

#### Task Breakdown

##### 3.1 Integrate Tesseract OCR as pipeline-lite backend
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No Tesseract integration. Only OCR engine is `PytorchPaddleOCR` at `mineru/model/ocr/pytorch_paddle.py`.
- **What to Build**:
  ```python
  # mineru/model/ocr/tesseract.py
  class TesseractOCRModel:
      def __init__(
          self,
          lang: str = "eng",
          oem: int = 3,  # OCR Engine Mode
          psm: int = 3,  # Page Segmentation Mode
          config: str = "",
      ):
          import pytesseract
          self.tesseract = pytesseract
          self.config = f"--oem {oem} --psm {psm} {config}"
          self.lang = lang
      
      def predict(self, img: np.ndarray) -> list[dict]:
          # Convert numpy array to PIL Image
          from PIL import Image
          pil_img = Image.fromarray(img)
          
          # Get OCR data
          data = self.tesseract.image_to_data(
              pil_img, lang=self.lang, config=self.config, output_type=Output.DICT
          )
          
          # Convert to MinerU format
          return self._format_output(data)
  ```
  - Add to `pyproject.toml`: `tesseract-ocr = ["pytesseract>=0.3.10"]`
  - Add Tesseract to `AtomicModel` enum in `mineru/backend/pipeline/model_list.py`
  - Update `model_init.py` to support Tesseract
  - Add Tesseract language data download utility
- **Files to Create**:
  - `mineru/model/ocr/tesseract.py` - Tesseract model wrapper
  - `mineru/model/ocr/__init__.py` - Export both engines
- **Files to Modify**:
  - `mineru/backend/pipeline/model_list.py` - Add TESSERACT to AtomicModel enum
  - `mineru/backend/pipeline/model_init.py` - Add Tesseract initialization
  - `mineru/backend/pipeline/batch_analyze.py` - Add Tesseract batch inference
  - `pyproject.toml` - Add `[tesseract]` optional dependency
- **Priority**: 🔴 CRITICAL - Requested feature

##### 3.2 Add EasyOCR as alternative OCR engine
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No EasyOCR integration.
- **What to Build**:
  ```python
  # mineru/model/ocr/easyocr.py
  class EasyOCRModel:
      def __init__(
          self,
          lang_list: list[str] = ["en"],
          gpu: bool = True,
          model_storage_directory: str | None = None,
          download_enabled: bool = True,
      ):
          import easyocr
          self.reader = easyocr.Reader(
              lang_list, gpu=gpu, model_storage_directory=model_storage_directory
          )
      
      def predict(self, img: np.ndarray) -> list[dict]:
          results = self.reader.readtext(img)
          return self._format_output(results)
  ```
  - 80+ languages supported
  - Good for handwritten text
  - Add `[easyocr]` optional dependency
- **Files to Create**:
  - `mineru/model/ocr/easyocr.py`
- **Priority**: 🟡 HIGH

##### 3.3 Implement PaddleOCR optimizations
- **Status**: ⚠️ PARTIAL
- **Current State**: `PytorchPaddleOCR` is a PyTorch reimplementation. No INT8 quantization or TensorRT support.
- **What to Build**:
  - INT8 quantization for OCR model weights
  - TensorRT export for GPU inference (2-5x speedup)
  - ONNX export for cross-platform deployment
  - Benchmark suite comparing FP32 vs INT8 vs TensorRT
- **Files to Modify**:
  - `mineru/model/ocr/pytorch_paddle.py` - Add quantization support
- **Priority**: 🟡 HIGH

##### 3.4 Add RapidOCR as lightweight alternative
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: `RapidTable` exists (table recognition), but NOT `RapidOCR`.
- **What to Build**:
  ```python
  # mineru/model/ocr/rapidocr.py
  class RapidOCRModel:
      def __init__(self, lang: str = "ch"):
          from rapidocr_onnx import RapidOCR
          self.ocr = RapidOCR(lang=lang)
      
      def predict(self, img: np.ndarray) -> list[dict]:
          result, elapse = self.ocr(img)
          return self._format_output(result)
  ```
  - No PaddlePaddle dependency (pure ONNX Runtime)
  - Fast startup, low memory
  - Good for CPU-only deployments
- **Files to Create**:
  - `mineru/model/ocr/rapidocr.py`
- **Priority**: 🟡 HIGH

##### 3.5 Create modular pipeline components
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/backend/pipeline/model_list.py` - `AtomicModel` enum (Layout, MFD, MFR, OCR, WirelessTable, WiredTable, TableCls, ImgOrientationCls)
  - `mineru/backend/pipeline/model_init.py` - `AtomModelSingleton` for each component
  - `mineru/backend/pipeline/batch_analyze.py` - Batch inference logic
  - **Gaps**: Cannot selectively enable/disable components at runtime
- **What to Build**:
  - Runtime component toggle (enable layout detection only, disable OCR)
  - Component dependency graph (layout → OCR → table)
  - Custom component pipeline (user-specified order)
- **Files to Modify**:
  - `mineru/backend/pipeline/model_init.py` - Add component enable/disable
- **Priority**: 🟢 MEDIUM

##### 3.6 Implement pipeline-lite mode
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No lite mode.
- **What to Build**:
  - Minimal model set: layout detection + Tesseract OCR only
  - No formula recognition, no table recognition, no orientation classification
  - Fast startup (<5s), low memory (<2GB)
  - CPU-optimized
  - Backend name: `"pipeline-lite"`
  ```python
  # Usage
  from mineru import MinerU
  
  ocr = MinerU(backend="pipeline-lite", lang="en")
  result = ocr.process("document.pdf")  # Fast, CPU-only
  ```
- **Files to Create**:
  - `mineru/backend/pipeline/lite_config.py` - Lite mode config
  - `mineru/backend/pipeline/lite_model_init.py` - Minimal model init
- **Priority**: 🔴 CRITICAL

##### 3.7 Add pipeline accuracy vs speed tradeoff configuration
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No speed/accuracy controls.
- **What to Build**:
  ```python
  # Config options
  config = {
      "pipeline_mode": "fast",  # "fast", "balanced", "accurate"
      "layout_confidence_threshold": 0.5,  # Lower = more detections
      "ocr_confidence_threshold": 0.5,
      "max_pages_for_vlm": 10,  # Switch to VLM for short docs
      "enable_refinement": False,  # Post-processing refinement
  }
  ```
- **Files to Modify**:
  - `mineru/backend/pipeline/pipeline_analyze.py` - Add mode selection
- **Priority**: 🟢 MEDIUM

##### 3.8 Create pipeline component benchmarking suite
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No benchmarking utilities.
- **What to Build**:
  - `mineru/benchmarks/pipeline.py` - Benchmark script
  - Compare: Tesseract vs PaddleOCR vs EasyOCR vs RapidOCR
  - Metrics: latency, accuracy (CER/WER), memory usage
  - Export to CSV/JSON
  - CLI: `mineru-benchmark --backend pipeline --engines tesseract,paddle`
- **Files to Create**:
  - `mineru/benchmarks/__init__.py`
  - `mineru/benchmarks/pipeline.py`
- **Priority**: 🟢 MEDIUM

---

### Module 4: Multi-Model VLM Backend

**Goal**: Support multiple VLM models (dots.mocr, Qwen2-VL, InternVL2, Got-OCR2.0, Nougat) with auto-selection, model hub, and ensemble voting.

**Current Status**: 18.2% Complete (1 implemented, 2 partial, 8 not started)

#### Task Breakdown

##### 4.1 Design VLM model interface
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: VLM backend has `doc_analyze()` function but no abstract interface for models.
- **What to Build**:
  ```python
  # mineru/backend/vlm/base.py
  class VLMModelProtocol(Protocol):
      """Protocol for all VLM models"""
      
      @abstractmethod
      async def predict(
          self,
          images: list[np.ndarray],
          prompt: str,
          **kwargs
      ) -> list[str]:
          """Run inference on batch of images"""
          ...
      
      @abstractmethod
      def get_model_name(self) -> str:
          """Return model identifier"""
          ...
      
      @abstractmethod
      def get_supported_languages(self) -> list[str]:
          """Return supported language codes"""
          ...
      
      @abstractmethod
      def get_optimal_batch_size(self) -> int:
          """Return recommended batch size"""
          ...
  ```
- **Files to Create**:
  - `mineru/backend/vlm/base.py` - VLMModelProtocol
- **Priority**: 🔴 CRITICAL

##### 4.2 Add dots.mocr model support
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/backend/vlm/dots_ocr/` - Complete dots.ocr module
  - `mineru/backend/vlm/dots_ocr_client.py` - `DotsOCRClient` with `batch_two_step_extract()`, `aio_batch_two_step_extract()`
  - Supports `transformers`, `vllm-engine`, `vllm-async-engine`, `lmdeploy-engine`, `mlx-engine`
  - Prompt modes: `prompt_layout_all_en`, `prompt_layout_only_en`
  - **Gaps**: No model versioning, no config validation
- **What to Build**: (Enhance existing implementation)
  - Add model version tracking
  - Add config validation
  - Improve error messages
- **Files to Modify**:
  - `mineru/backend/vlm/dots_ocr/` - Add validation
- **Priority**: 🟢 MEDIUM

##### 4.3 Integrate Qwen2-VL
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No Qwen2-VL integration.
- **What to Build**:
  ```python
  # mineru/backend/vlm/models/qwen2_vl.py
  class Qwen2VLModel:
      def __init__(
          self,
          model_path: str,
          device: str = "cuda",
          engine: str = "transformers",
      ):
          from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
          self.model = Qwen2VLForConditionalGeneration.from_pretrained(model_path)
          self.processor = AutoProcessor.from_pretrained(model_path)
          ...
  ```
  - Support 2B, 7B, 72B variants
  - Strong multilingual support
  - Good for general document understanding
- **Files to Create**:
  - `mineru/backend/vlm/models/__init__.py`
  - `mineru/backend/vlm/models/qwen2_vl.py`
- **Priority**: 🟡 HIGH

##### 4.4 Add InternVL2/2.5 support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Not integrated.
- **What to Build**:
  - InternVL2-2B, 8B, 26B, 76B variants
  - Strong table and formula understanding
  - Add to model registry
- **Files to Create**:
  - `mineru/backend/vlm/models/internvl.py`
- **Priority**: 🟡 HIGH

##### 4.5 Integrate Got-OCR2.0
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Not integrated.
- **What to Build**:
  - Specialized for OCR tasks
  - High accuracy on printed text
  - Good fallback option
- **Files to Create**:
  - `mineru/backend/vlm/models/got_ocr.py`
- **Priority**: 🟢 MEDIUM

##### 4.6 Add Nougat model support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Not integrated.
- **What to Build**:
  - Specialized for scientific papers (LaTeX output)
  - Sequence-to-sequence architecture
  - Good for academic document processing
  ```python
  # mineru/backend/vlm/models/nougat.py
  class NougatModel:
      def __init__(self, model_path: str):
          from transformers import VisionEncoderDecoderModel
          self.model = VisionEncoderDecoderModel.from_pretrained(model_path)
  ```
- **Files to Create**:
  - `mineru/backend/vlm/models/nougat.py`
- **Priority**: 🟢 MEDIUM

##### 4.7 Implement model auto-selection
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: User must specify model manually.
- **What to Build**:
  ```python
  def auto_select_model(
      doc_type: str,  # "invoice", "paper", "book", "form", "receipt"
      lang: str,
      has_formulas: bool,
      has_tables: bool,
      available_vram: float,  # GB
  ) -> str:
      if doc_type == "paper" and has_formulas:
          return "nougat"
      if lang in ["zh", "en"] and available_vram >= 10:
          return "dots.mocr"
      if has_tables:
          return "internvl2"
      return "qwen2-vl"
  ```
- **Files to Create**:
  - `mineru/backend/vlm/model_selector.py`
- **Priority**: 🟡 HIGH

##### 4.8 Create model hub
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `mineru/utils/models_download_utils.py` - Download from HuggingFace/ModelScope
  - `mineru/cli/models_download.py` - CLI for downloading
  - `ModelPath` enum in `mineru/utils/enum_class.py` - Lists model paths
  - **Gaps**: No versioning, no caching, no integrity verification, no model metadata
- **What to Build**:
  - Model version tracking
  - Download resume/retry
  - SHA256 checksum verification
  - Model metadata (size, license, intended use, performance metrics)
  - Local model cache with LRU eviction
- **Files to Modify**:
  - `mineru/utils/models_download_utils.py` - Add versioning, checksums
  - `mineru/utils/enum_class.py` - Add model metadata
- **Priority**: 🟡 HIGH

##### 4.9 Add custom model fine-tuning interface
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No fine-tuning support.
- **What to Build**:
  - Export fine-tuned models to MinerU format
  - Training script templates
  - Dataset preparation utilities
  - `mineru finetune --model dots.mocr --data ./dataset`
- **Files to Create**:
  - `mineru/finetune/` - Fine-tuning module
- **Priority**: 🔵 LOW

##### 4.10 Implement model ensemble voting
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No ensemble support.
- **What to Build**:
  - Run multiple models on same input
  - Vote on conflicting outputs
  - Confidence scoring
  - Useful for critical extractions (tables, formulas)
- **Files to Create**:
  - `mineru/backend/vlm/ensemble.py`
- **Priority**: 🔵 LOW

##### 4.11 Add model comparison and evaluation utilities
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No comparison tools.
- **What to Build**:
  - `mineru evaluate --model1 dots.mocr --model2 qwen2-vl --dataset ./test_pdfs`
  - Compare CER, WER, table accuracy, formula accuracy
  - Export results to CSV/HTML
- **Files to Create**:
  - `mineru/evaluate.py`
- **Priority**: 🟢 MEDIUM

---

### Module 5: Inference Engine Integration

**Goal**: Support multiple inference engines (vLLM, LMDeploy, Ollama, MLX, TGI) with auto-detection and fallback.

**Current Status**: 44.4% Complete (3 implemented, 2 partial, 4 not started)

#### Task Breakdown

##### 5.1 Integrate vLLM engine
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/cli/vlm_server.py` - `mineru-vllm-server` entry point
  - `mineru/backend/vlm/vlm_analyze.py` - `vllm-engine`, `vllm-async-engine` support
  - `mineru/utils/engine_utils.py` - vLLM utilities
  - **Gaps**: No KV cache optimization, no continuous batching tuning
- **What to Build**: (See Module 7 for KV cache optimizations)
- **Priority**: 🟢 MEDIUM

##### 5.2 Add LMDeploy engine support
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/cli/vlm_server.py` - `mineru-lmdeploy-server` entry point
  - `mineru/backend/vlm/vlm_analyze.py` - `lmdeploy-engine` support
  - `set_lmdeploy_backend()` in `mineru/backend/vlm/utils.py`
  - **Gaps**: Limited documentation
- **What to Build**: Improve documentation, add benchmarking
- **Priority**: 🟢 MEDIUM

##### 5.3 Integrate Ollama
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No Ollama integration.
- **What to Build**:
  ```python
  # mineru/backend/vlm/engines/ollama.py
  class OllamaEngine:
      def __init__(
          self,
          model: str = "qwen2-vl:7b",
          base_url: str = "http://localhost:11434",
      ):
          from ollama import Client
          self.client = Client(host=base_url)
          self.model = model
      
      async def predict(self, images: list[np.ndarray], prompt: str) -> list[str]:
          # Convert images to base64
          # Call Ollama API
          ...
  ```
  - Easy local deployment
  - Good for development/testing
  - Add `[ollama]` optional dependency
- **Files to Create**:
  - `mineru/backend/vlm/engines/ollama.py`
- **Priority**: 🟡 HIGH

##### 5.4 Add Transformers.js support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No browser/JS support.
- **What to Build**:
  - HTTP endpoint that runs Transformers.js models
  - Useful for edge deployments
  - Lower accuracy, but runs anywhere
- **Files to Create**:
  - `mineru/backend/vlm/engines/transformers_js.py`
- **Priority**: 🔵 LOW

##### 5.5 Implement MLX engine for Apple Silicon
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/backend/vlm/vlm_analyze.py` - `mlx-engine` support
  - macOS only (Apple Silicon M1/M2/M3)
  - **Gaps**: Limited model support
- **What to Build**: Expand model compatibility
- **Priority**: 🟢 MEDIUM

##### 5.6 Add TGI (Text Generation Inference) support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No TGI integration.
- **What to Build**:
  - HuggingFace TGI server support
  - Production-grade serving
  - Good for enterprise deployments
- **Files to Create**:
  - `mineru/backend/vlm/engines/tgi.py`
- **Priority**: 🟡 HIGH

##### 5.7 Create HTTP/OpenAI-compatible client
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/backend/vlm/dots_ocr_client.py` - OpenAI-compatible client
  - `vlm-http-client` and `hybrid-http-client` backend options
  - Uses `openai` Python package
  - **Gaps**: No retry logic, no timeout handling
- **What to Build**: Add retry, timeout, connection pooling
- **Priority**: 🟡 HIGH

##### 5.8 Implement engine auto-detection and fallback
- **Status**: ⚠️ PARTIAL
- **Current State**: Engine name is specified via CLI `--engine` parameter. No auto-detection.
- **What to Build**:
  ```python
  def auto_detect_engine(model_name: str, device: str) -> str:
      if device == "mps":
          return "mlx-engine"
      if "dots-ocr" in model_name:
          return "vllm-async-engine"
      return "transformers"
  ```
- **Files to Modify**:
  - `mineru/utils/engine_utils.py` - Add auto-detection
- **Priority**: 🟡 HIGH

##### 5.9 Add engine-specific configuration templates
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No templates.
- **What to Build**:
  ```yaml
  # mineru-engine-configs.yaml
  engines:
    vllm:
      gpu_memory_utilization: 0.5
      tensor_parallel_size: 1
      max_model_len: 8192
      enable_chunked_prefill: true
    
    lmdeploy:
      session_len: 8192
      max_batch_size: 8
      cache_max_entry_count: 0.8
  ```
- **Files to Create**:
  - `mineru/backend/vlm/engine_configs.yaml`
- **Priority**: 🟢 MEDIUM

---

### Module 6: Memory & Performance Optimization

**Goal**: Optimize memory usage, implement lazy loading, streaming processing, and prevent OOM errors.

**Current Status**: 27.3% Complete (2 implemented, 2 partial, 7 not started)

#### Task Breakdown

##### 6.1 Implement model lazy loading
- **Status**: ⚠️ PARTIAL
- **Current State**: Models are loaded on first use via singletons (`ModelSingleton`, `AtomModelSingleton`, `HybridModelSingleton`). This is lazy loading, but uncontrolled.
- **What to Build**:
  - Explicit control: `load_models=True/False` in constructor
  - Batch lazy loading (load only needed components)
  - Progress callbacks during loading
- **Files to Modify**:
  - `mineru/backend/vlm/vlm_analyze.py` - ModelSingleton
  - `mineru/backend/pipeline/model_init.py` - AtomModelSingleton
- **Priority**: 🟡 HIGH

##### 6.2 Add model unloading and memory release
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No model unloading. `clean_memory(device)` in `mineru/utils/model_utils.py` only clears cache, doesn't unload models.
- **What to Build**:
  ```python
  # mineru/utils/model_utils.py
  def unload_model(model: Any, device: str):
      """Completely unload model and free memory"""
      del model
      if device.startswith("cuda"):
          torch.cuda.empty_cache()
          torch.cuda.reset_peak_memory_stats()
      gc.collect()
  
  # Add to BackendProtocol
  async def shutdown(self) -> None:
      """Unload models and release resources"""
      unload_model(self.model, self.device)
  ```
- **Files to Modify**:
  - `mineru/utils/model_utils.py` - Add unload utilities
  - All backend classes - Add `shutdown()` method
- **Priority**: 🟡 HIGH

##### 6.3 Create memory pool for image buffers and tensors
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No memory pooling.
- **What to Build**:
  - Pre-allocate image buffers
  - Reuse tensors across pages
  - Reduce memory fragmentation
- **Files to Create**:
  - `mineru/utils/memory_pool.py`
- **Priority**: 🟢 MEDIUM

##### 6.4 Implement streaming PDF processing
- **Status**: ⚠️ PARTIAL
- **Current State**: `aio_do_parse()` in `mineru/cli/common.py` supports async processing, but entire PDF is loaded into memory.
- **What to Build**:
  - Page-by-page processing
  - Never load entire PDF into memory
  - Stream results as they complete
  ```python
  async for page_result in ocr.process_stream("large_document.pdf"):
      save_result(page_result)
  ```
- **Files to Modify**:
  - `mineru/cli/common.py` - Add streaming mode
  - `mineru/utils/pdf_reader.py` - Add page iterator
- **Priority**: 🟡 HIGH

##### 6.5 Add VRAM-aware batch sizing
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `mineru/utils/model_utils.py` - `get_vram(device)` and batch sizing logic
  - 32GB→16, 16GB→8, 12GB→4, 8GB→2, <8GB→1
  - `set_default_batch_size()` in `mineru/backend/vlm/utils.py`
  - **Gaps**: Not dynamic (doesn't adjust during processing)
- **What to Build**:
  - Real-time VRAM monitoring
  - Dynamic batch size adjustment
  - Backpressure when VRAM is low
- **Files to Modify**:
  - `mineru/utils/model_utils.py` - Add dynamic sizing
- **Priority**: 🟡 HIGH

##### 6.6 Implement garbage collection tuning
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: `gc.collect()` called manually in some places.
- **What to Build**:
  - Automatic GC after batch processing
  - Disable GC during inference (performance)
  - Force GC when memory pressure is high
- **Files to Modify**:
  - `mineru/backend/pipeline/batch_analyze.py` - Add GC tuning
- **Priority**: 🟢 MEDIUM

##### 6.7 Create memory usage profiling tools
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No profiling tools.
- **What to Build**:
  - `mineru profile-memory --backend pipeline document.pdf`
  - Show memory usage per component
  - Identify memory leaks
  - Export to HTML report
- **Files to Create**:
  - `mineru/utils/memory_profiler.py`
- **Priority**: 🟢 MEDIUM

##### 6.8 Add OOM prevention with backpressure
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No OOM prevention beyond batch sizing.
- **What to Build**:
  - Memory limit configuration
  - Pause processing when memory > threshold
  - Resume when memory drops
  - Graceful degradation
- **Files to Create**:
  - `mineru/utils/oom_prevention.py`
- **Priority**: 🟡 HIGH

##### 6.9 Implement model weight sharing
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Each backend instance loads its own models.
- **What to Build**:
  - Share model weights across backend instances
  - Reference counting for shared models
  - Reduce memory for multi-backend setups
- **Priority**: 🔵 LOW

##### 6.10 Add device abstraction and auto-selection
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/utils/config_reader.py` - `get_device()` function
  - Supports: cpu, cuda, cuda:N, npu, mps, gcu, musa, mlu, sdaa
  - `MINERU_DEVICE_MODE` environment variable
  - **Gaps**: No automatic performance benchmarking per device
- **Priority**: 🟢 MEDIUM

##### 6.11 Implement mixed precision inference
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No FP16/INT8/FP8 support.
- **What to Build**:
  - FP16 inference for supported models
  - INT8 quantization for CPU inference
  - FP8 for next-gen GPUs (H100, RTX 4090)
- **Priority**: 🟡 HIGH

---

### Module 7: KV Cache Optimization System

**Goal**: Optimize KV cache usage for VLM bulk processing with sharing, pre-allocation, intelligent eviction, and paged attention.

**Current Status**: 0% Complete (0 implemented, 0 partial, 11 not started)

#### Task Breakdown

##### 7.1 Analyze KV cache usage patterns
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No KV cache analysis. vLLM default settings are used.
- **What to Build**:
  - Profile KV cache usage across different document types
  - Measure cache hit rates for similar pages
  - Identify cache size vs performance tradeoffs
  - Document findings
- **Files to Create**:
  - `mineru/backend/vlm/kv_cache_analysis.py`
- **Priority**: 🔴 CRITICAL - Prerequisite for other KV cache tasks

##### 7.2 Implement KV cache sharing for similar pages
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No cache sharing.
- **What to Build**:
  - Detect similar pages (layout, content type)
  - Share KV cache prefix for similar pages
  - Reduce redundant computation
  ```python
  # Example: All pages with same template share prefix cache
  if page.layout_hash in cache_registry:
      reuse_cache(cache_registry[page.layout_hash])
  ```
- **Files to Create**:
  - `mineru/backend/vlm/kv_cache_sharing.py`
- **Priority**: 🟡 HIGH

##### 7.3 Add KV cache pre-allocation for bulk jobs
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No pre-allocation.
- **What to Build**:
  - Pre-allocate KV cache before bulk processing
  - Avoid runtime cache expansion
  - Configure via `--kv-cache-size` parameter
- **Files to Modify**:
  - `mineru/cli/vlm_server.py` - Add pre-allocation
- **Priority**: 🟡 HIGH

##### 7.4 Create intelligent KV cache eviction policies
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: vLLM default eviction.
- **What to Build**:
  - LRU (Least Recently Used)
  - LFU (Least Frequently Used)
  - Priority-based (keep high-priority jobs in cache)
  - Configurable eviction strategy
- **Files to Create**:
  - `mineru/backend/vlm/kv_cache_eviction.py`
- **Priority**: 🟡 HIGH

##### 7.5 Implement vLLM KV cache tuning
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Default vLLM settings.
- **What to Build**:
  - `block_size`: Optimize for document processing (default 16)
  - `num_gpu_blocks`: Auto-calculate based on VRAM
  - `num_cpu_blocks`: CPU swap space
  - `enable_chunked_prefill`: Enable for better throughput
  ```python
  # vLLM config
  engine_args = AsyncLLMEngine(
      model=model_path,
      block_size=16,
      gpu_memory_utilization=0.5,
      max_num_seqs=256,
      enable_chunked_prefill=True,
  )
  ```
- **Files to Modify**:
  - `mineru/backend/vlm/vlm_analyze.py` - Add tuning parameters
- **Priority**: 🔴 CRITICAL

##### 7.6 Add page similarity detection for cache reuse
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No similarity detection.
- **What to Build**:
  - Layout hash (based on block types, positions)
  - Content embedding similarity
  - Image hash for similar images
  - Cache similar page prefixes
- **Files to Create**:
  - `mineru/backend/vlm/page_similarity.py`
- **Priority**: 🟡 HIGH

##### 7.7 Implement batch-aware KV cache management
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No batch-aware management.
- **What to Build**:
  - Allocate cache based on batch size
  - Release cache after batch completes
  - Overlap cache load with inference
- **Priority**: 🟡 HIGH

##### 7.8 Create KV cache metrics
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No metrics.
- **What to Build**:
  - Hit/miss ratio
  - Cache utilization %
  - Fragmentation %
  - Eviction rate
  - Export to Prometheus
- **Files to Create**:
  - `mineru/backend/vlm/kv_cache_metrics.py`
- **Priority**: 🟡 HIGH

##### 7.9 Add continuous batching optimization
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: vLLM has built-in continuous batching, but not tuned for OCR.
- **What to Build**:
  - Tune `max_num_batched_tokens`
  - Optimize for variable-length sequences
  - Balance latency vs throughput
- **Priority**: 🟡 HIGH

##### 7.10 Implement paged attention configuration
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: vLLM uses paged attention by default, but not optimized.
- **What to Build**:
  - Configure page size for document processing
  - Optimize for typical sequence lengths
  - Reduce memory fragmentation
- **Priority**: 🟡 HIGH

##### 7.11 Add KV cache persistence across restarts
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Cache is lost on restart.
- **What to Build**:
  - Save frequently-used cache prefixes to disk
  - Load on startup
  - Useful for recurring document types
- **Priority**: 🔵 LOW

---

### Module 8: Bulk Processing & Job Management

**Goal**: Enable high-throughput bulk document processing with job queues, priority support, progress tracking, and checkpoint/resume.

**Current Status**: 13.6% Complete (1 implemented, 1 partial, 9 not started)

#### Task Breakdown

##### 8.1 Design bulk processing API
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Only single-file or directory-based processing via CLI.
- **What to Build**:
  ```python
  # Bulk API
  from mineru import BulkProcessor
  
  processor = BulkProcessor(
      backend="pipeline",
      max_concurrent=4,
      batch_size=8,
  )
  
  # Submit job
  job = processor.submit("batch_pdfs/*.pdf")
  
  # Check status
  print(job.status)  # "running", "completed", "failed"
  print(job.progress)  # 45/100 pages
  
  # Get results
  results = job.wait_and_get_results()
  ```
- **Files to Create**:
  - `mineru/bulk.py` - BulkProcessor class
  - `mineru/job.py` - Job tracking
- **Priority**: 🟡 HIGH

##### 8.2 Implement Redis/Celery job queue
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No job queue system.
- **What to Build**:
  - Celery workers for OCR processing
  - Redis as message broker
  - Result backend (Redis or database)
  - Horizontal scaling (add more workers)
  ```python
  # celery_config.py
  from celery import Celery
  
  app = Celery(
      "mineru",
      broker="redis://localhost:6379/0",
      backend="redis://localhost:6379/1",
  )
  
  @app.task
  def process_pdf(pdf_bytes: bytes, config: dict) -> dict:
      from mineru import MinerU
      ocr = MinerU(**config)
      return ocr.process_bytes(pdf_bytes)
  ```
- **Files to Create**:
  - `mineru/celery_app.py`
  - `mineru/tasks.py` - Celery tasks
- **Priority**: 🟡 HIGH

##### 8.3 Add priority queue support
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No priority support.
- **What to Build**:
  - Priority levels: critical, high, normal, low
  - Separate queues per priority
  - Preempt low-priority jobs for critical ones
- **Priority**: 🟢 MEDIUM

##### 8.4 Create dynamic batch sizing
- **Status**: ⚠️ PARTIAL
- **Current State**: Static batch sizing based on VRAM (see M6.5).
- **What to Build**:
  - Real-time resource monitoring
  - Adjust batch size based on:
    - Available VRAM
    - Queue depth
    - Processing latency
    - Memory pressure
- **Priority**: 🟡 HIGH

##### 8.5 Implement progress tracking with ETA
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No progress tracking.
- **What to Build**:
  ```python
  job = processor.submit(files)
  
  for event in job.stream_events():
      if event.type == "progress":
          print(f"{event.completed}/{event.total} pages")
          print(f"ETA: {event.eta}")
          print(f"Throughput: {event.pages_per_sec} pages/sec")
  ```
- **Files to Create**:
  - `mineru/progress.py` - Progress tracker
- **Priority**: 🟡 HIGH

##### 8.6 Add checkpoint and resume for interrupted jobs
- **Status**: ✅ IMPLEMENTED (CLI only)
- **Current State**:
  - CLI has `--resume` and `--no-resume` flags
  - Checkpoints stored in `.mineru_checkpoints/` directory
  - Tracks processed and failed files in JSON
  - **Gaps**: No API-level checkpoint, no bulk job resume
- **What to Build**:
  - API-level checkpoint
  - Resume bulk jobs from failure point
  - Configurable checkpoint interval
- **Files to Modify**:
  - `mineru/cli/common.py` - Extract checkpoint logic
  - `mineru/checkpoint.py` - Shared checkpoint module
- **Priority**: 🟡 HIGH

##### 8.7 Implement parallel page processing
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Sequential page processing.
- **What to Build**:
  ```python
  # Process pages in parallel
  results = await asyncio.gather(*[
      process_page(page, backend)
      for page in pdf_pages
  ])
  ```
  - Configurable concurrency
  - GPU memory management
  - Out-of-order completion
- **Priority**: 🟡 HIGH

##### 8.8 Create bulk processing metrics dashboard
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No dashboard.
- **What to Build**:
  - Web dashboard (Gradio or custom)
  - Show: active jobs, queue depth, throughput, errors
  - Real-time updates via WebSocket
- **Priority**: 🟢 MEDIUM

##### 8.9 Add rate limiting and backpressure
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No rate limiting for bulk processing.
- **What to Build**:
  - Limit concurrent bulk jobs
  - Throttle job submission rate
  - Backpressure when queue is full
- **Priority**: 🟡 HIGH

##### 8.10 Implement result caching and deduplication
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No caching.
- **What to Build**:
  - Hash input PDF
  - Cache results (Redis or disk)
  - Skip duplicate processing
  - Configurable TTL
- **Priority**: 🟢 MEDIUM

##### 8.11 Add job scheduling
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No scheduling.
- **What to Build**:
  - Schedule recurring jobs (cron-like)
  - Example: Process new invoices every day at 6 AM
  - Job dependencies
- **Priority**: 🔵 LOW

---

### Module 9: Docker & Deployment Services

**Goal**: Create production-ready Docker deployment with multi-architecture support, Kubernetes manifests, and auto-scaling.

**Current Status**: 45.5% Complete (4 implemented, 2 partial, 5 not started)

#### Task Breakdown

##### 9.1 Create production FastAPI service
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/cli/fast_api.py` - `mineru-api` entry point
  - `/file_parse` endpoint with file upload
  - Concurrency control via `MINERU_API_MAX_CONCURRENT_REQUESTS`
  - Multiple response formats (markdown, middle_json, model_output, content_list, images)
  - ZIP export option
  - OpenAPI documentation at `/docs`
  - **Gaps**: No authentication, no rate limiting, no webhook support
- **Priority**: 🟢 MEDIUM

##### 9.2 Implement multi-backend API routing
- **Status**: ⚠️ PARTIAL
- **Current State**: Backend is selected via `backend` form parameter in `/file_parse`.
- **What to Build**:
  - Dedicated endpoints: `/ocr/pipeline`, `/ocr/vlm`, `/ocr/hybrid`
  - Backend-specific parameters
  - Backend health endpoint
  ```python
  @app.post("/ocr/pipeline")
  async def ocr_pipeline(
      file: UploadFile,
      ocr_engine: str = Form("paddle"),
      ...
  ):
      ...
  ```
- **Priority**: 🟡 HIGH

##### 9.3 Add health check endpoints
- **Status**: ⚠️ PARTIAL
- **Current State**: No dedicated health endpoints. Docker Compose has `curl -f http://localhost:30000/health` for vLLM server, but MinerU FastAPI doesn't implement it.
- **What to Build**:
  ```python
  @app.get("/health")
  async def health():
      return {"status": "ok"}
  
  @app.get("/ready")
  async def ready():
      # Check if models are loaded
      return {"status": "ready", "backends": BackendRegistry.list_available()}
  
  @app.get("/live")
  async def live():
      return {"status": "alive"}
  
  @app.get("/metrics")
  async def metrics():
      return {
          "pages_processed": ...,
          "avg_latency": ...,
          "memory_usage": ...,
      }
  ```
- **Priority**: 🟡 HIGH

##### 9.4 Create multi-stage Dockerfile
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `docker/global/Dockerfile` - Global x86_64 build
  - `docker/china/*.Dockerfile` - Platform-specific builds (NPU, DCU, GCU, PPU, MLU, MUSA, MACA, COREX, KXPU)
  - Base: `vllm/vllm-openai:v0.10.1.1`
  - Installs: `mineru[core]>=2.7.0`, fonts
  - Downloads all models
  - **Gaps**: No multi-stage build (large image size), no CPU-only variant, no slim variant
- **What to Build**:
  - Multi-stage build (build stage, runtime stage)
  - CPU-only variant
  - Slim variant (no models, download on demand)
  - GPU variants per architecture
- **Files to Modify**:
  - `docker/global/Dockerfile` - Convert to multi-stage
- **Priority**: 🟡 HIGH

##### 9.5 Implement Docker Compose stack
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `docker/compose.yaml` - Three services:
    - `mineru-openai-server` (port 30000) - vLLM server
    - `mineru-api` (port 8000) - FastAPI
    - `mineru-gradio` (port 7860) - Gradio UI
  - GPU reservations, health checks
  - Profiles for selective startup
  - **Gaps**: No Redis, no monitoring (Prometheus/Grafana), no worker autoscaling
- **What to Build**:
  - Add Redis service (job queue)
  - Add Prometheus service
  - Add Grafana service
  - Add Celery worker service
  - Production-ready compose file
- **Priority**: 🟡 HIGH

##### 9.6 Add Kubernetes manifests
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No K8s manifests.
- **What to Build**:
  - `k8s/deployment.yaml` - MinerU deployment
  - `k8s/service.yaml` - ClusterIP/LoadBalancer service
  - `k8s/hpa.yaml` - Horizontal Pod Autoscaler
  - `k8s/configmap.yaml` - Configuration
  - `k8s/pvc.yaml` - Persistent volume for models
  - `k8s/ingress.yaml` - Ingress routing
- **Files to Create**:
  - `k8s/` directory with all manifests
- **Priority**: 🟡 HIGH

##### 9.7 Create Helm chart
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No Helm chart.
- **What to Build**:
  - `helm/mineru/Chart.yaml`
  - `helm/mineru/values.yaml` - Configurable values
  - `helm/mineru/templates/` - Templates
  - Support:
    - Replica count
    - GPU allocation
    - Model preloading
    - Autoscaling
    - Ingress
- **Files to Create**:
  - `helm/mineru/` - Complete Helm chart
- **Priority**: 🟢 MEDIUM

##### 9.8 Implement graceful shutdown
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No graceful shutdown.
- **What to Build**:
  - Finish processing current requests
  - Reject new requests
  - Unload models
  - Clean up temp files
  ```python
  @app.on_event("shutdown")
  async def shutdown_event():
      logger.info("Shutting down gracefully...")
      # Wait for active requests to complete
      await asyncio.sleep(grace_period)
      # Unload models
      await backend.shutdown()
  ```
- **Priority**: 🟡 HIGH

##### 9.9 Add structured logging with correlation IDs
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Uses `loguru` with basic formatting. No correlation IDs.
- **What to Build**:
  - JSON structured logging
  - Correlation ID per request (propagate across services)
  - Request/response logging
  - Log levels by endpoint
  ```python
  @app.middleware("http")
  async def add_correlation_id(request, call_next):
      correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
      response = await call_next(request)
      response.headers["X-Correlation-ID"] = correlation_id
      return response
  ```
- **Priority**: 🟡 HIGH

##### 9.10 Create cloud deployment guides
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No deployment guides.
- **What to Build**:
  - AWS: EKS, ECS, SageMaker
  - GCP: GKE, Cloud Run, Vertex AI
  - Azure: AKS, Container Instances
  - Step-by-step instructions
  - Terraform templates
- **Priority**: 🟢 MEDIUM

##### 9.11 Implement auto-scaling
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No auto-scaling.
- **What to Build**:
  - K8s HPA based on:
    - Queue depth (Redis)
    - GPU utilization
    - Request latency
  - Scale to zero when idle
  - Scale up on demand
- **Priority**: 🟢 MEDIUM

---

### Module 10: API Server Features

**Goal**: Add production API features: authentication, rate limiting, WebSocket, webhooks, caching, versioning.

**Current Status**: 30% Complete (2 implemented, 2 partial, 6 not started)

#### Task Breakdown

##### 10.1 Implement authentication
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No authentication.
- **What to Build**:
  - API key authentication
  - JWT token support
  - OAuth2 for enterprise
  ```python
  from fastapi.security import APIKeyHeader
  
  api_key_header = APIKeyHeader(name="X-API-Key")
  
  async def verify_api_key(api_key: str = Depends(api_key_header)):
      if api_key not in VALID_API_KEYS:
          raise HTTPException(status_code=401, detail="Invalid API key")
  ```
- **Priority**: 🟡 HIGH

##### 10.2 Add rate limiting
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Only concurrency limiting via semaphore.
- **What to Build**:
  - Token bucket algorithm
  - Per-API-key rate limits
  - Configurable limits
  ```python
  # SlowAPI integration
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  
  limiter = Limiter(key_func=get_remote_address)
  
  @app.post("/file_parse")
  @limiter.limit("10/minute")
  async def parse_pdf(request: Request, ...):
      ...
  ```
- **Priority**: 🟡 HIGH

##### 10.3 Create WebSocket endpoint
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No WebSocket.
- **What to Build**:
  ```python
  @app.websocket("/ws/job/{job_id}")
  async def job_progress_websocket(websocket: WebSocket, job_id: str):
      await websocket.accept()
      while job.is_running():
          await websocket.send_json(job.get_progress())
          await asyncio.sleep(1)
  ```
- **Priority**: 🟢 MEDIUM

##### 10.4 Implement webhook callbacks
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No webhooks.
- **What to Build**:
  ```python
  # Submit job with webhook
  job = processor.submit(files, webhook_url="https://example.com/callback")
  
  # On completion
  async def notify_webhook(job: Job):
      await httpx.post(job.webhook_url, json=job.get_result())
  ```
- **Priority**: 🟢 MEDIUM

##### 10.5 Add file upload validation
- **Status**: ⚠️ PARTIAL
- **Current State**: Basic file handling in FastAPI. No size limits, type validation, or malware scanning.
- **What to Build**:
  - Max file size (configurable)
  - File type validation (PDF, images only)
  - MIME type checking
  - Malware scanning (ClamAV integration)
- **Priority**: 🟡 HIGH

##### 10.6 Create request/response caching
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No caching.
- **What to Build**:
  - Redis caching layer
  - Cache identical requests
  - Configurable TTL
  - Cache invalidation
- **Priority**: 🟢 MEDIUM

##### 10.7 Implement API versioning
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No versioning.
- **What to Build**:
  - URL versioning: `/v1/file_parse`, `/v2/file_parse`
  - Header versioning: `API-Version: 1`
  - Backward compatibility guarantees
  - Deprecation warnings
- **Priority**: 🟡 HIGH

##### 10.8 Add CORS configuration
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No CORS middleware.
- **What to Build**:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://example.com"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Priority**: 🟡 HIGH

##### 10.9 Create API usage analytics
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No analytics.
- **What to Build**:
  - Track API calls per user
  - Track processing time
  - Track error rates
  - Export to billing system
- **Priority**: 🟢 MEDIUM

##### 10.10 Implement request timeout enforcement
- **Status**: ⚠️ PARTIAL
- **Current State**: No explicit timeout.
- **What to Build**:
  ```python
  @app.post("/file_parse")
  async def parse_pdf(request: Request, ...):
      try:
          async with asyncio.timeout(300):  # 5 minutes
              result = await aio_do_parse(...)
              return result
      except asyncio.TimeoutError:
          raise HTTPException(status_code=408, detail="Request timeout")
  ```
- **Priority**: 🟡 HIGH

---

### Module 11: Document Processing Pipeline

**Goal**: Add advanced document processing: preprocessing, type detection, language detection, page classification, table/formula extraction, image captioning.

**Current Status**: 31.8% Complete (3 implemented, 1 partial, 7 not started)

#### Task Breakdown

##### 11.1 Add PDF preprocessing
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No preprocessing.
- **What to Build**:
  - Deskew (correct rotated pages)
  - Denoise (remove artifacts)
  - Contrast enhancement
  - Binarization
  - Border removal
  ```python
  from mineru.preprocessing import enhance_page
  
  enhanced_img = enhance_page(
      image,
      deskew=True,
      denoise=True,
      enhance_contrast=True,
  )
  ```
- **Priority**: 🟡 HIGH

##### 11.2 Implement document type detection
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No type detection.
- **What to Build**:
  - Classify: invoice, paper, book, form, receipt, contract
  - Auto-select backend based on type
  - Adjust processing parameters
- **Priority**: 🟡 HIGH

##### 11.3 Create language detection
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/utils/language.py` - Language detection utilities
  - `fast-langdetect` package
  - **Gaps**: Could be more accurate for mixed-language documents
- **Priority**: 🟢 MEDIUM

##### 11.4 Add page classification
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No page-level classification.
- **What to Build**:
  - Classify: text-heavy, image-heavy, mixed, formula-heavy, table-heavy
  - Adjust processing pipeline per page type
- **Priority**: 🟡 HIGH

##### 11.5 Implement reading order optimization
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/utils/block_sort.py` - Reading order sorting
  - `layout_reader`, xycut algorithms
  - `ModelSingleton` for layout reader
  - **Gaps**: Could be improved for complex layouts
- **Priority**: 🟢 MEDIUM

##### 11.6 Create table detection and structure extraction
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/model/table/rec/slanet_plus/` - SlanetPlus (wired tables)
  - `mineru/model/table/rec/unet_table/` - UnetTableModel (wireless tables)
  - `mineru/model/table/cls/` - Table classification
  - `mineru/utils/table_merge.py` - Table merging utilities
  - `mineru/utils/format_utils.py` - OTSL-to-HTML conversion
  - **Gaps**: Could support more table types
- **Priority**: 🟢 MEDIUM

##### 11.7 Add formula detection and LaTeX conversion
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/model/mfd/yolo_v8.py` - Formula detection (YOLOv8)
  - `mineru/model/mfr/unimernet/` - Formula recognition (Unimernet)
  - Supports inline and display formulas
  - **Gaps**: Formula refinement, LaTeX quality
- **Priority**: 🟢 MEDIUM

##### 11.8 Implement image captioning
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No image captioning.
- **What to Build**:
  - Generate alt-text for images
  - VLM-based captioning
  - Configurable detail level
- **Priority**: 🟢 MEDIUM

##### 11.9 Add metadata extraction
- **Status**: ⚠️ PARTIAL
- **Current State**: PDF metadata via `pypdf`, but not exposed in output.
- **What to Build**:
  - Title, author, creation date
  - Keywords, subject
  - Page count, language
  - Include in output JSON
- **Priority**: 🟢 MEDIUM

##### 11.10 Create document structure tree
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No structured tree output.
- **What to Build**:
  ```json
  {
    "document": {
      "title": "Paper Title",
      "sections": [
        {
          "heading": "1. Introduction",
          "level": 1,
          "content": [...]
        }
      ]
    }
  }
  ```
- **Priority**: 🟡 HIGH

##### 11.11 Implement multi-column layout detection
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Basic layout detection via DocLayoutYOLO.
- **What to Build**:
  - Detect multi-column layouts
  - Correct reading order across columns
  - Handle complex magazine/newspaper layouts
- **Priority**: 🟢 MEDIUM

---

### Module 12: Output Formats & Export

**Goal**: Support multiple output formats: Markdown, HTML, DOCX, searchable PDF, JSON, CSV, EPUB, LaTeX, RAG-ready chunks.

**Current Status**: 31.8% Complete (3 implemented, 1 partial, 7 not started)

#### Task Breakdown

##### 12.1 Enhanced Markdown output
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py` - `union_make()` for MM_MD, NLP_MD
  - `mineru/backend/vlm/vlm_middle_json_mkcontent.py` - VLM markdown
  - Includes: headings, text, tables (HTML), formulas (LaTeX), images
  - **Gaps**: No frontmatter, no metadata, no footnotes
- **What to Build**: Add YAML frontmatter, metadata, footnotes
- **Priority**: 🟢 MEDIUM

##### 12.2 Implement HTML export
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `mineru/utils/format_utils.py` - Table HTML conversion
  - **Gaps**: No full document HTML, no semantic tags, no accessibility
- **What to Build**:
  - Complete HTML document
  - Semantic tags (`<article>`, `<section>`, `<figure>`)
  - ARIA attributes for accessibility
  - CSS styling
- **Priority**: 🟡 HIGH

##### 12.3 Add DOCX export
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No DOCX export.
- **What to Build**:
  ```python
  from docx import Document
  
  def export_to_docx(pdf_info: dict, output_path: str):
      doc = Document()
      for block in pdf_info["blocks"]:
          if block["type"] == "text":
              doc.add_paragraph(block["text"])
          elif block["type"] == "heading":
              doc.add_heading(block["text"], level=block["level"])
          elif block["type"] == "table":
              add_table_to_docx(block["table_body"], doc)
      doc.save(output_path)
  ```
  - Preserve styles (bold, italic)
  - Add images
  - Add tables
- **Files to Create**:
  - `mineru/export/docx.py`
- **Priority**: 🟡 HIGH

##### 12.4 Create searchable PDF export
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No searchable PDF.
- **What to Build**:
  - OCR text as invisible layer over original PDF
  - Use `pypdfium2` or `pikepdf`
  - Preserves original layout
  - Text is selectable/searchable
- **Priority**: 🟡 HIGH

##### 12.5 Implement JSON structured output
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - `*_middle.json` - Intermediate JSON with full structure
  - `*_model.json` - Model raw output
  - `*_content_list.json` - Simplified content list
  - **Gaps**: No schema validation, no documentation
- **What to Build**: Add JSON schema, validation
- **Priority**: 🟢 MEDIUM

##### 12.6 Add CSV/TSV export
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No CSV export.
- **What to Build**:
  - Extract tables to CSV
  - Extract text to CSV
  - Useful for data extraction pipelines
- **Priority**: 🟢 MEDIUM

##### 12.7 Create EPUB export
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No EPUB export.
- **What to Build**:
  - Convert to EPUB for e-book readers
  - Preserve structure
  - Add metadata
- **Priority**: 🔵 LOW

##### 12.8 Implement LaTeX export
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Formulas are LaTeX, but document structure is not.
- **What to Build**:
  - Full LaTeX document
  - Sections, subsections
  - Tables as LaTeX tables
  - Formulas inline/display
  - Useful for academic papers
- **Priority**: 🟢 MEDIUM

##### 12.9 Add RAG-ready chunked output
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No RAG output.
- **What to Build**:
  ```json
  {
    "chunks": [
      {
        "id": "chunk_1",
        "text": "...",
        "metadata": {
          "page": 1,
          "section": "Introduction",
          "type": "text"
        },
        "embedding": [0.1, 0.2, ...]
      }
    ]
  }
  ```
  - Semantic chunking
  - Include embeddings
  - Metadata for filtering
- **Priority**: 🟡 HIGH

##### 12.10 Create custom output templates
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No templating.
- **What to Build**:
  ```python
  from jinja2 import Template
  
  template = Template(open("my_template.md.j2").read())
  output = template.render(pdf_info=pdf_info)
  ```
- **Priority**: 🟢 MEDIUM

##### 12.11 Implement streaming output
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No streaming output.
- **What to Build**:
  - Stream results as they complete
  - Useful for large documents
  - Reduce latency to first result
- **Priority**: 🟡 HIGH

---

### Module 13: Testing & Quality Assurance

**Goal**: Comprehensive test coverage, E2E tests, load testing, benchmarking, CI/CD pipeline.

**Current Status**: 25% Complete (2 implemented, 1 partial, 7 not started)

#### Task Breakdown

##### 13.1 Expand unit test coverage to >85%
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**:
  - `tests/unittest/test_e2e.py` - Only E2E test for pipeline backend
  - Tests: txt and ocr parse methods
  - Uses fuzzy matching for validation
  - **Gaps**: No unit tests, coverage unknown, no tests for VLM/hybrid backends (commented out)
- **What to Build**:
  - Unit tests for all modules
  - Mock external dependencies
  - Test edge cases
  - Measure coverage with `pytest-cov`
  - Target: >85% coverage
- **Priority**: 🔴 CRITICAL

##### 13.2 Create integration tests for API endpoints
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No API integration tests.
- **What to Build**:
  - Test all FastAPI endpoints
  - Test file upload, form parameters
  - Test error handling
  - Use `httpx` async client for testing
  ```python
  from fastapi.testclient import TestClient
  from mineru.cli.fast_api import app
  
  client = TestClient(app)
  
  def test_file_parse():
      with open("test.pdf", "rb") as f:
          response = client.post(
              "/file_parse",
              files={"files": ("test.pdf", f, "application/pdf")},
          )
      assert response.status_code == 200
  ```
- **Priority**: 🟡 HIGH

##### 13.3 Add E2E tests for all backend combinations
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: Only pipeline backend tested.
- **What to Build**:
  - Test: pipeline, vlm, hybrid backends
  - Test: txt, ocr, auto parse methods
  - Test: all supported output formats
  - Use sample PDFs from `tests/unittest/pdfs/`
- **Priority**: 🟡 HIGH

##### 13.4 Implement load testing suite
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No load testing.
- **What to Build**:
  - Locust load testing scripts
  - Test: concurrent requests, sustained load, spike load
  - Measure: latency, throughput, error rate
  ```python
  # locustfile.py
  from locust import HttpUser, task, between
  
  class MinerUUser(HttpUser):
      wait_time = between(1, 3)
      
      @task
      def parse_pdf(self):
          self.client.post(
              "/file_parse",
              files={"files": open("test.pdf", "rb")},
          )
  ```
- **Priority**: 🟡 HIGH

##### 13.5 Add memory leak detection tests
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No memory leak tests.
- **What to Build**:
  - Run 1000+ requests
  - Monitor memory growth
  - Detect leaks early
  - Use `tracemalloc`, `memory_profiler`
- **Priority**: 🟡 HIGH

##### 13.6 Create benchmark suite
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No benchmark suite.
- **What to Build**:
  - Compare all backends
  - Compare all models
  - Compare all engines
  - Metrics: latency, accuracy, memory
  - Export to CSV/HTML
- **Priority**: 🟡 HIGH

##### 13.7 Implement OCR accuracy regression tests
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No accuracy regression tests.
- **What to Build**:
  - Golden dataset with ground truth
  - Calculate CER (Character Error Rate)
  - Calculate WER (Word Error Rate)
  - Fail if accuracy drops below threshold
- **Priority**: 🟡 HIGH

##### 13.8 Add CI/CD pipeline
- **Status**: ✅ IMPLEMENTED (partial)
- **Current State**:
  - `.github/workflows/python-package.yml` - Build and release
  - `.github/workflows/cli.yml` - CLI tests
  - `.github/workflows/mkdocs.yml` - Documentation
  - `.github/workflows/cla.yml` - CLA checking
  - **Gaps**: No test coverage enforcement, no linting, no Docker build in CI
- **What to Build**:
  - Add `pytest` to CI
  - Add coverage threshold
  - Add `ruff` linting
  - Add `mypy` type checking
  - Add Docker build test
- **Priority**: 🟡 HIGH

##### 13.9 Create golden dataset
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No golden dataset.
- **What to Build**:
  - 100+ annotated PDFs
  - Ground truth for: text, tables, formulas, images
  - Multiple languages
  - Multiple document types
- **Priority**: 🟡 HIGH

##### 13.10 Implement visual diff testing
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No visual testing.
- **What to Build**:
  - Compare detected layout bboxes with ground truth
  - Calculate IoU (Intersection over Union)
  - Visualize differences
- **Priority**: 🟢 MEDIUM

---

### Module 14: Monitoring & Observability

**Goal**: Complete observability stack: Prometheus metrics, Grafana dashboards, distributed tracing, alerting, audit logging.

**Current Status**: 5.6% Complete (0 implemented, 1 partial, 8 not started)

#### Task Breakdown

##### 14.1 Integrate Prometheus metrics
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No Prometheus integration.
- **What to Build**:
  ```python
  from prometheus_client import Counter, Histogram, generate_latest
  
  REQUEST_COUNT = Counter("mineru_requests_total", "Total requests", ["backend", "status"])
  REQUEST_LATENCY = Histogram("mineru_request_latency_seconds", "Request latency", ["backend"])
  PAGES_PROCESSED = Counter("mineru_pages_processed_total", "Total pages processed", ["backend"])
  
  @app.get("/metrics")
  async def metrics():
      return Response(content=generate_latest(), media_type="text/plain")
  ```
- **Priority**: 🟡 HIGH

##### 14.2 Add custom metrics
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No custom metrics.
- **What to Build**:
  - Pages per second
  - Backend selection distribution
  - Error rates by type
  - Model load time
  - Queue depth
- **Priority**: 🟡 HIGH

##### 14.3 Create Grafana dashboards
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No dashboards.
- **What to Build**:
  - Pre-built Grafana JSON dashboards
  - Import via Docker Compose
  - Dashboards:
    - Overview (requests, latency, errors)
    - Backend performance
    - Resource usage (CPU, GPU, memory)
    - Business metrics (cost/page)
- **Priority**: 🟢 MEDIUM

##### 14.4 Implement distributed tracing
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No tracing.
- **What to Build**:
  - OpenTelemetry integration
  - Jaeger/Zipkin backend
  - Trace requests across services
  - Identify bottlenecks
- **Priority**: 🟢 MEDIUM

##### 14.5 Add alerting rules
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No alerting.
- **What to Build**:
  - Prometheus Alertmanager rules
  - Alert on:
    - High error rate
    - High latency (p95, p99)
    - Low memory
    - Queue backlog
    - Model failures
- **Priority**: 🟢 MEDIUM

##### 14.6 Create audit logging
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No audit logging.
- **What to Build**:
  - Log all API requests
  - Include: user, timestamp, parameters, result status
  - Immutable log
  - Compliance ready
- **Priority**: 🟡 HIGH

##### 14.7 Implement performance profiling middleware
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No profiling middleware.
- **What to Build**:
  ```python
  @app.middleware("http")
  async def profile_request(request, call_next):
      start = time.time()
      response = await call_next(request)
      duration = time.time() - start
      if duration > 10:  # Slow request
          logger.warning(f"Slow request: {request.url.path} took {duration:.2f}s")
      return response
  ```
- **Priority**: 🟢 MEDIUM

##### 14.8 Add business metrics
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No business metrics.
- **What to Build**:
  - Cost per page (GPU time, API calls)
  - GPU utilization %
  - Revenue per day (if billing)
  - Customer satisfaction (if feedback)
- **Priority**: 🟢 MEDIUM

##### 14.9 Create log aggregation integration
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No log aggregation.
- **What to Build**:
  - ELK stack (Elasticsearch, Logstash, Kibana)
  - Grafana Loki integration
  - Structured JSON logging
  - Log retention policies
- **Priority**: 🟢 MEDIUM

---

### Module 15: Developer Experience & Documentation

**Goal**: Comprehensive documentation, tutorials, examples, interactive API explorer, migration guides.

**Current Status**: 35% Complete (3 implemented, 1 partial, 6 not started)

#### Task Breakdown

##### 15.1 Create comprehensive API reference documentation
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No API reference docs.
- **What to Build**:
  - Auto-generate from docstrings (Sphinx, MkDocs)
  - Document all public classes, methods, functions
  - Include examples for each API
- **Priority**: 🟡 HIGH

##### 15.2 Write quickstart guides
- **Status**: ⚠️ PARTIAL
- **Current State**:
  - `README.md` - Basic installation and CLI usage
  - `README_zh-CN.md` - Chinese version
  - **Gaps**: No library quickstart, no Docker quickstart, no API quickstart
- **What to Build**:
  - Quickstart: Library (pip install, basic usage)
  - Quickstart: Docker (docker compose up, API calls)
  - Quickstart: API (curl examples)
- **Priority**: 🟡 HIGH

##### 15.3 Add code examples and tutorials
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No tutorials.
- **What to Build**:
  - Jupyter notebooks:
    - Basic OCR usage
    - Backend selection
    - Bulk processing
    - Custom configuration
    - Docker deployment
  - Example scripts in `examples/` directory
- **Priority**: 🟡 HIGH

##### 15.4 Create architecture diagrams
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No architecture diagrams.
- **What to Build**:
  - System architecture overview
  - Backend flow diagrams
  - Docker deployment architecture
  - Data flow diagrams
- **Priority**: 🟢 MEDIUM

##### 15.5 Add migration guides
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No migration guides.
- **What to Build**:
  - Migrate from Tesseract → MinerU
  - Migrate from EasyOCR → MinerU
  - Migrate from PaddleOCR → MinerU
  - Migrate from Unstructured → MinerU
- **Priority**: 🟢 MEDIUM

##### 15.6 Create troubleshooting guide
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No troubleshooting guide.
- **What to Build**:
  - Common errors and solutions
  - FAQ
  - Known issues
  - How to report bugs
- **Priority**: 🟡 HIGH

##### 15.7 Add video tutorials
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No videos.
- **What to Build**:
  - Installation and setup
  - Basic usage
  - Advanced configuration
  - Docker deployment
- **Priority**: 🔵 LOW

##### 15.8 Implement interactive API explorer
- **Status**: ✅ IMPLEMENTED
- **Current State**:
  - FastAPI auto-generates Swagger at `/docs`
  - Redoc at `/redoc`
  - Can be disabled via `MINERU_API_ENABLE_FASTAPI_DOCS=0`
  - **Gaps**: No examples in schema
- **Priority**: 🟢 MEDIUM

##### 15.9 Create cookbook
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No cookbook.
- **What to Build**:
  - Common patterns and recipes
  - Copy-paste ready code
  - Real-world use cases
- **Priority**: 🟡 HIGH

##### 15.10 Add changelog automation
- **Status**: ❌ NOT IMPLEMENTED
- **Current State**: No CHANGELOG.md.
- **What to Build**:
  - `CHANGELOG.md` following Keep a Changelog format
  - Auto-generate from git commits
  - Release notes automation
- **Priority**: 🟢 MEDIUM

---

## Recommended Implementation Order

### Wave 1: Foundation (Weeks 1-4)

**Priority**: Establish library foundation and critical missing features

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M1 | 1.1 Unified public API | 3 days | Foundation for library usage |
| 2 | M1 | 1.2 High-level OCR class | 3 days | Core user interface |
| 3 | M1 | 1.4 Exception hierarchy | 1 day | Error handling |
| 4 | M2 | 2.1 BackendProtocol interface | 3 days | Enables pluggable backends |
| 5 | M2 | 2.2 BackendRegistry | 2 days | Backend discovery |
| 6 | M3 | **3.1 Tesseract integration** | 5 days | **Requested feature** |
| 7 | M3 | **3.6 Pipeline-lite mode** | 3 days | **Requested feature** |
| 8 | M9 | 9.3 Health check endpoints | 1 day | Docker deployment ready |
| 9 | M9 | 9.8 Graceful shutdown | 1 day | Production readiness |
| 10 | M1 | 1.8 PyPI packaging | 2 days | Distribution ready |

**Deliverables**: 
- ✅ `pip install mineru` works
- ✅ `from mineru import MinerU` works
- ✅ Tesseract backend available
- ✅ Pipeline-lite mode available
- ✅ Docker service has health checks

---

### Wave 2: Multi-Model VLM Support (Weeks 5-8)

**Priority**: Expand VLM backend options

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M4 | 4.1 VLM model interface | 2 days | Foundation for multi-model |
| 2 | M4 | 4.3 Qwen2-VL integration | 4 days | Popular alternative |
| 3 | M4 | 4.4 InternVL2 integration | 4 days | Strong table support |
| 4 | M4 | 4.7 Model auto-selection | 2 days | User-friendly |
| 5 | M5 | 5.3 Ollama integration | 3 days | Easy local deployment |
| 6 | M5 | 5.6 TGI support | 3 days | Enterprise serving |
| 7 | M5 | 5.8 Engine auto-detection | 1 day | User-friendly |
| 8 | M4 | 4.8 Model hub enhancement | 3 days | Model management |
| 9 | M6 | 6.2 Model unloading | 2 days | Memory management |
| 10 | M1 | 1.5 Type hints | 3 days | Developer experience |

**Deliverables**:
- ✅ 4+ VLM models supported
- ✅ 6+ inference engines
- ✅ Auto-selection works
- ✅ Model memory management

---

### Wave 3: Memory & Performance (Weeks 9-12)

**Priority**: Optimize for production use

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M7 | **7.1 KV cache analysis** | 3 days | **Foundation for optimization** |
| 2 | M7 | **7.5 vLLM KV cache tuning** | 3 days | **Immediate performance gain** |
| 3 | M6 | 6.4 Streaming PDF processing | 3 days | Large document support |
| 4 | M6 | 6.5 VRAM-aware batch sizing | 2 days | Dynamic optimization |
| 5 | M6 | 6.8 OOM prevention | 2 days | Stability |
| 6 | M6 | 6.11 Mixed precision | 3 days | Speed up inference |
| 7 | M7 | 7.2 KV cache sharing | 4 days | Bulk processing optimization |
| 8 | M7 | 7.4 Cache eviction policies | 3 days | Efficient cache use |
| 9 | M7 | 7.6 Page similarity detection | 3 days | Enable cache sharing |
| 10 | M6 | 6.1 Lazy loading control | 2 days | Faster startup |

**Deliverables**:
- ✅ 50%+ memory reduction for bulk jobs
- ✅ No OOM errors
- ✅ Streaming processing
- ✅ KV cache optimized

---

### Wave 4: Bulk Processing & Docker Service (Weeks 13-16)

**Priority**: Production deployment ready

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M8 | 8.1 Bulk processing API | 3 days | Foundation for bulk jobs |
| 2 | M8 | 8.2 Redis/Celery queue | 4 days | Scalable processing |
| 3 | M8 | 8.5 Progress tracking | 2 days | User visibility |
| 4 | M8 | 8.6 Checkpoint/resume | 2 days | Reliability |
| 5 | M9 | 9.2 Multi-backend routing | 2 days | API organization |
| 6 | M9 | 9.4 Multi-stage Dockerfile | 3 days | Smaller images |
| 7 | M9 | 9.5 Enhanced Docker Compose | 2 days | Easy deployment |
| 8 | M10 | 10.1 Authentication | 2 days | Security |
| 9 | M10 | 10.2 Rate limiting | 2 days | Abuse prevention |
| 10 | M10 | 10.7 API versioning | 1 day | Backward compatibility |

**Deliverables**:
- ✅ Bulk API works
- ✅ Job queue scalable
- ✅ Docker compose production-ready
- ✅ API secure

---

### Wave 5: Output Formats & Document Processing (Weeks 17-20)

**Priority**: Expand capabilities

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M12 | 12.3 DOCX export | 3 days | Common request |
| 2 | M12 | 12.4 Searchable PDF | 3 days | Common request |
| 3 | M12 | 12.9 RAG-ready chunks | 3 days | AI/ML pipelines |
| 4 | M12 | 12.2 HTML export | 2 days | Web integration |
| 5 | M11 | 11.1 PDF preprocessing | 2 days | Improve accuracy |
| 6 | M11 | 11.2 Document type detection | 3 days | Auto-configuration |
| 7 | M11 | 11.10 Document structure tree | 3 days | Structured output |
| 8 | M3 | 3.2 EasyOCR integration | 3 days | More OCR options |
| 9 | M3 | 3.4 RapidOCR integration | 3 days | CPU-friendly |
| 10 | M1 | 1.3 Configuration system | 3 days | User-friendly config |

**Deliverables**:
- ✅ 6+ output formats
- ✅ Document preprocessing
- ✅ Auto-configuration
- ✅ Structured output

---

### Wave 6: Testing, Monitoring & Documentation (Weeks 21-24)

**Priority**: Production readiness

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M13 | 13.1 Unit tests >85% | 5 days | Quality assurance |
| 2 | M13 | 13.2 API integration tests | 3 days | API reliability |
| 3 | M13 | 13.4 Load testing | 3 days | Performance validation |
| 4 | M14 | 14.1 Prometheus metrics | 3 days | Observability |
| 5 | M14 | 14.2 Custom metrics | 2 days | Business insights |
| 6 | M14 | 14.6 Audit logging | 2 days | Compliance |
| 7 | M15 | 15.2 Quickstart guides | 2 days | User onboarding |
| 8 | M15 | 15.3 Tutorials/examples | 4 days | Learning resources |
| 9 | M15 | 15.6 Troubleshooting guide | 2 days | Support reduction |
| 10 | M13 | 13.8 CI/CD enhancement | 2 days | Automation |

**Deliverables**:
- ✅ 85%+ test coverage
- ✅ Full observability stack
- ✅ Comprehensive docs
- ✅ CI/CD automated

---

### Wave 7: Polish & Advanced Features (Weeks 25+)

**Priority**: Nice-to-have features

| Priority | Module | Task | Effort | Rationale |
|----------|--------|------|--------|-----------|
| 1 | M7 | 7.3 KV cache pre-allocation | 2 days | Advanced optimization |
| 2 | M7 | 7.9 Continuous batching | 2 days | Throughput |
| 3 | M8 | 8.3 Priority queues | 2 days | Job prioritization |
| 4 | M9 | 9.6 Kubernetes manifests | 4 days | K8s deployment |
| 5 | M9 | 9.7 Helm chart | 3 days | K8s packaging |
| 6 | M10 | 10.3 WebSocket | 2 days | Real-time updates |
| 7 | M11 | 11.8 Image captioning | 3 days | Accessibility |
| 8 | M12 | 12.8 LaTeX export | 2 days | Academic use |
| 9 | M4 | 4.6 Nougat model | 3 days | Scientific papers |
| 10 | M15 | 15.9 Cookbook | 3 days | Developer experience |

**Deliverables**:
- ✅ Advanced optimizations
- ✅ K8s ready
- ✅ Niche use cases covered

---

## Getting Started

### For Contributors

1. **Fork the repository**: `git clone https://github.com/your-username/MinerU-dots.git`
2. **Set up development environment**:
   ```bash
   cd MinerU-dots
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,test]"
   ```
3. **Pick a module**: Choose from the modules above based on your expertise and interest
4. **Create a feature branch**: `git checkout -b feature/module-X-task-Y`
5. **Implement and test**: Follow the detailed task descriptions
6. **Submit a PR**: Include tests and documentation updates

### Priority Tasks for Immediate Work

🔴 **CRITICAL** (Start these first):
1. **M1.1** - Unified public API (foundation)
2. **M2.1** - BackendProtocol interface (enables plugin architecture)
3. **M3.1** - Tesseract integration (requested feature)
4. **M3.6** - Pipeline-lite mode (requested feature)
5. **M7.1** - KV cache analysis (prerequisite for optimization)
6. **M13.1** - Unit tests (quality foundation)

### Communication

- **Questions**: Open a GitHub Discussion or issue
- **Design decisions**: Propose in issue comments before implementation
- **Progress updates**: Comment on relevant issue
- **Code reviews**: All PRs require review

---

## Appendix: Current Codebase Quick Reference

### Key Files and Directories

```
mineru/
├── __init__.py                          # ⚠️ Empty - needs exports
├── cli/
│   ├── common.py                        # ✅ do_parse, aio_do_parse
│   ├── fast_api.py                      # ✅ FastAPI server
│   ├── vlm_server.py                    # ✅ vLLM/LMDeploy servers
│   └── models_download.py               # ✅ Model download CLI
├── backend/
│   ├── pipeline/                        # ✅ Pipeline backend
│   │   ├── pipeline_analyze.py          # Main entry point
│   │   ├── model_init.py                # Model initialization
│   │   └── model_list.py                # AtomicModel enum
│   ├── vlm/                             # ✅ VLM backend
│   │   ├── vlm_analyze.py               # Main entry point
│   │   ├── dots_ocr/                    # dots.ocr module
│   │   └── dots_ocr_client.py           # HTTP client
│   └── hybrid/                          # ✅ Hybrid backend
│       └── hybrid_analyze.py            # Main entry point
├── model/
│   ├── ocr/pytorch_paddle.py            # ✅ Current OCR engine
│   ├── layout/doclayoutyolo.py          # ✅ Layout detection
│   ├── mfd/yolo_v8.py                   # ✅ Formula detection
│   ├── mfr/unimernet/                   # ✅ Formula recognition
│   └── table/                           # ✅ Table recognition
├── data/
│   ├── data_reader_writer/              # ✅ I/O abstractions
│   └── io.py                            # ✅ Additional I/O
├── utils/
│   ├── config_reader.py                 # ⚠️ Config reading
│   ├── model_utils.py                   # ⚠️ Memory management
│   ├── format_utils.py                  # ✅ Format conversion
│   └── models_download_utils.py         # ⚠️ Model downloads
└── version.py                           # ✅ Version info

docker/
├── global/Dockerfile                    # ⚠️ Single-stage build
├── china/*.Dockerfile                   # ✅ Platform-specific
└── compose.yaml                         # ⚠️ Basic services

tests/
└── unittest/
    └── test_e2e.py                      # ⚠️ Limited coverage
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MINERU_DEVICE_MODE` | Device selection | auto-detect |
| `MINERU_VIRTUAL_VRAM_SIZE` | VRAM limit | auto-detect |
| `MINERU_MODEL_SOURCE` | Model source | huggingface |
| `MINERU_API_MAX_CONCURRENT_REQUESTS` | API concurrency | 0 (unlimited) |
| `MINERU_HYBRID_BATCH_RATIO` | Hybrid batch ratio | auto |
| `MINERU_LOG_LEVEL` | Logging level | INFO |

---

**Document Version**: 1.0  
**Last Updated**: April 8, 2026  
**Maintainer**: @surya  
**Status**: Living Document - Update as tasks are completed
