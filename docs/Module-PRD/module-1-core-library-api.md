# PRD: Module 1 - Core Library & API Foundation

## Problem Statement

As a developer wanting to use MinerU in my Python projects, I can't simply `import mineru` and call an OCR function. The current codebase only exposes CLI commands (`mineru`, `mineru-api`, `mineru-gradio`, etc.) — there's no clean, importable Python library interface. To use MinerU programmatically, I'd need to dig into internal modules like `mineru.cli.common.do_parse()`, figure out the right parameters, manually construct data readers/writers, and handle resource cleanup myself. This makes MinerU unusable as a library dependency in other projects.

## Solution

Create a clean, high-level Python library API on top of the existing CLI infrastructure. Users will be able to `from mineru import MinerU`, configure it with a fluent builder, process PDFs synchronously or asynchronously, and get structured results — all without touching CLI internals. The existing CLI commands will become thin wrappers over the new library API.

## User Stories

1. As a developer, I want to `from mineru import MinerU` and call `ocr.process("document.pdf")`, so that I can use MinerU as a Python library in my projects.

2. As a developer, I want to use MinerU as a context manager (`with MinerU(...) as ocr:`), so that resources (models, GPU memory) are automatically cleaned up when I'm done.

3. As a developer, I want an async client (`AsyncMinerU`), so that I can process multiple PDFs concurrently in an asyncio application.

4. As a developer, I want a fluent config builder (`Config().set_backend("pipeline").set_device("cuda")...`), so that I can programmatically construct and validate configurations without editing JSON files or setting environment variables.

5. As a developer, I want a clear exception hierarchy (`MinerUError`, `BackendError`, `ModelLoadError`, etc.), so that I can catch and handle specific error types in my application.

6. As a developer, I want type hints on all public APIs, so that my IDE provides autocomplete and mypy/Pyright can type-check my code.

7. As a developer, I want to choose output formats (`"mm_markdown"`, `"nlp_markdown"`, `"content_list"`), so that I get the result structure I need.

8. As a developer, I want to pass PDFs as file paths, `Path` objects, or raw bytes, so that I can process documents from disk, S3, or in-memory streams.

9. As a developer, I want to receive structured results (Pydantic models or typed dicts), so that I can programmatically access page info, blocks, spans, and tables without parsing JSON strings.

10. As a developer, I want to process batches of PDFs with a single call (`ocr.process_batch(["a.pdf", "b.pdf"])`), so that I don't have to write my own loop.

11. As a developer, I want to check which backends are available (`ocr.get_available_backends()`), so that I know what options I have before processing.

12. As a developer, I want to get processing progress callbacks, so that I can show progress bars or log status during long-running jobs.

13. As a user, I want to install MinerU via `pip install mineru` from PyPI, so that I don't need to clone the repo to use it.

14. As a developer, I want the existing CLI commands (`mineru`, `mineru-api`, etc.) to continue working exactly as before, so that upgrading doesn't break my scripts.

## Implementation Decisions

### 1. Public API Surface

The public API will be defined in `mineru/__init__.py` and export only these symbols:

```python
# mineru/__init__.py
from .version import __version__
from .client import MinerU
from .async_client import AsyncMinerU
from .config import Config
from .exceptions import (
    MinerUError,
    BackendError,
    ModelLoadError,
    ConfigurationError,
    InputError,
    ProcessingError,
    TimeoutError,
)
from .result import OCRResult, PageInfo, BlockInfo
from .data import DataReader, DataWriter, FileBasedDataReader, FileBasedDataWriter

__all__ = [
    "__version__",
    "MinerU",
    "AsyncMinerU",
    "Config",
    "MinerUError",
    "BackendError",
    "ModelLoadError",
    "ConfigurationError",
    "InputError",
    "ProcessingError",
    "TimeoutError",
    "OCRResult",
    "PageInfo",
    "BlockInfo",
    "DataReader",
    "DataWriter",
    "FileBasedDataReader",
    "FileBasedDataWriter",
]
```

### 2. MinerU Class (Sync Client)

**File**: `mineru/client.py`

The `MinerU` class is a high-level wrapper around the existing `do_parse()` function in `mineru/cli/common.py`. It provides:

```python
class MinerU:
    """High-level OCR processor."""

    def __init__(
        self,
        backend: str = "pipeline",
        lang: str = "en",
        device: str | None = None,       # auto-detect if None
        config: Config | None = None,
        output_format: str = "mm_markdown",
        formula_enable: bool = True,
        table_enable: bool = True,
        **kwargs,
    ): ...

    def process(
        self,
        input_path: str | Path | bytes,
        output_dir: str | Path | None = None,
        method: str = "auto",             # "auto", "txt", "ocr"
        draw_layout_bbox: bool = False,
        draw_span_bbox: bool = False,
        dump_md: bool = True,
        dump_content_list: bool = False,
        dump_middle_json: bool = False,
        dump_model_output: bool = False,
        dump_orig_pdf: bool = False,
        callback: Callable[[int, int], None] | None = None,  # progress
    ) -> OCRResult: ...

    def process_batch(
        self,
        input_paths: list[str | Path | bytes],
        output_dir: str | Path,
        method: str = "auto",
        **kwargs,
    ) -> list[OCRResult]: ...

    def get_available_backends(self) -> list[str]: ...
    def get_version(self) -> str: ...

    # Context manager
    def __enter__(self) -> "MinerU": ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
```

**Key design decisions:**
- Constructor accepts all configuration; `process()` accepts all output options
- `device` auto-detection uses existing `get_device()` from `config_reader`
- `process()` returns `OCRResult` (structured result object) regardless of output format
- If `output_dir` is None, results are written to temp directory and returned in-memory
- `callback(progress, total)` for progress reporting
- Context manager calls `cleanup()` on exit (model unload, memory release)

### 3. AsyncMinerU Class (Async Client)

**File**: `mineru/async_client.py`

Mirrors `MinerU` but uses `aio_do_parse()` from `mineru/cli/common.py`:

```python
class AsyncMinerU:
    """Async high-level OCR processor."""

    async def process(
        self,
        input_path: str | Path | bytes,
        output_dir: str | Path | None = None,
        method: str = "auto",
        **kwargs,
    ) -> OCRResult: ...

    async def process_batch(
        self,
        input_paths: list[str | Path | bytes],
        output_dir: str | Path,
        **kwargs,
    ) -> list[OCRResult]: ...

    async def __aenter__(self) -> "AsyncMinerU": ...
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
```

### 4. Config Builder

**File**: `mineru/config.py`

Fluent builder that wraps and unifies the existing config sources (`~/.mineru.json`, env vars, defaults):

```python
class Config:
    """Hierarchical configuration builder."""

    def __init__(self): ...

    def set_backend(self, backend: str) -> "Config": ...
    def set_device(self, device: str) -> "Config": ...
    def set_language(self, lang: str) -> "Config": ...
    def set_output_format(self, fmt: str) -> "Config": ...
    def enable_formula(self) -> "Config": ...
    def disable_formula(self) -> "Config": ...
    def enable_tables(self) -> "Config": ...
    def disable_tables(self) -> "Config": ...
    def set_batch_size(self, size: int) -> "Config": ...
    def set_models_dir(self, path: str) -> "Config": ...

    def load_from_file(self, path: str) -> "Config": ...
    def load_from_env(self) -> "Config": ...

    def freeze(self) -> "Config": ...     # Make immutable
    def to_dict(self) -> dict: ...
```

**Config hierarchy (later overrides earlier):**
1. Hardcoded defaults
2. `~/.mineru.json` (if `load_from_file()` called)
3. Environment variables (if `load_from_env()` called)
4. Programmatic `.set_*()` calls

**Implementation**: Use Pydantic models for validation. The existing `mineru/data/utils/schemas.py` has `S3Config` and `PageInfo` — extend with `MinerUConfig` model.

### 5. Exception Hierarchy

**File**: `mineru/exceptions.py`

```python
class MinerUError(Exception):
    """Base exception for all MinerU errors."""

class BackendError(MinerUError):
    """Backend-related errors (invalid backend name, unavailable, etc.)."""

class ModelLoadError(BackendError):
    """Failed to load model weights."""

class ConfigurationError(MinerUError):
    """Invalid configuration values."""

class InputError(MinerUError):
    """Invalid input: file not found, unsupported format, corrupted PDF."""

class ProcessingError(MinerUError):
    """Error during OCR processing (model inference failure, etc.)."""

class TimeoutError(MinerUError):
    """Processing timeout."""
```

All existing scattered exceptions (`mineru/data/utils/exceptions.py`, etc.) should subclass from these.

### 6. Result Object

**File**: `mineru/result.py`

Structured result instead of raw JSON:

```python
class PageInfo(BaseModel):
    page_number: int
    width: float
    height: float

class BlockInfo(BaseModel):
    block_type: str
    bbox: tuple[float, float, float, float]
    content: str | None = None
    # ... other fields

class OCRResult:
    """Result of an OCR processing job."""

    def __init__(self, middle_json: dict, output_dir: Path): ...

    @property
    def pdf_info(self) -> list[PageInfo]: ...

    @property
    def num_pages(self) -> int: ...

    @property
    def output_dir(self) -> Path: ...

    def markdown(self) -> str: ...
    def content_list(self) -> list[dict]: ...
    def middle_json(self) -> dict: ...
    def get_page(self, page_num: int) -> dict: ...
```

### 7. Refactor Existing CLI to Use Library

The existing `mineru/cli/client.py` (Click-based CLI) and `mineru/cli/common.py` (`do_parse`, `aio_do_parse`) will be refactored:

- `do_parse()` and `aio_do_parse()` remain as internal functions (they contain the core logic)
- `mineru/cli/client.py` will import and use `MinerU` class instead of calling `do_parse()` directly
- CLI becomes a thin wrapper: parse Click options → create `MinerU` instance → call `process()`

This ensures backward compatibility — all existing CLI flags continue to work.

### 8. Type Hints and py.typed

- Create empty `mineru/py.typed` marker file
- Add `include_package_data = true` to `pyproject.toml`
- Add type hints to all public API files
- Run `mypy mineru/client.py mineru/async_client.py mineru/config.py mineru/exceptions.py mineru/result.py --strict` to verify

### 9. PyPI Packaging

Update `pyproject.toml`:

```toml
[tool.setuptools.package-data]
mineru = ["py.typed"]

[tool.setuptools.packages.find]
include = ["mineru*"]

[project]
# Add classifiers
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Text Processing :: Linguistic",
]
```

Existing entry points stay unchanged — they just use the new library internally.

### 10. Internal Functions to Wrap

The key internal functions that `MinerU` will call:

| Internal Function | Location | Used By |
|---|---|---|
| `do_parse()` | `mineru/cli/common.py` | `MinerU.process()` |
| `aio_do_parse()` | `mineru/cli/common.py` | `AsyncMinerU.process()` |
| `read_fn()` | `mineru/cli/common.py` | File reading |
| `prepare_env()` | `mineru/cli/common.py` | Output directory setup |
| `get_device()` | `mineru/utils/config_reader.py` | Device auto-detection |
| `get_vlm_engine()` | `mineru/utils/engine_utils.py` | VLM engine selection |
| `FileBasedDataWriter` | `mineru/data/data_reader_writer/filebase.py` | Output writing |

These functions have stable interfaces and will not change.

### 11. What NOT to Build (Out of Scope for This PRD)

- **Backend refactoring** — that's Module 2. This PRD assumes the current `do_parse()`/`aio_do_parse()` interface stays as-is.
- **Model changes** — no new models, no model registry.
- **Output format converters** — HTML, DOCX, EPUB export is Module 12.
- **Streaming processing** — page-by-page streaming is Module 6.
- **Bulk job queue** — Redis/Celery integration is Module 8.
- **Memory management** — model unload utilities are Module 6.

## Testing Decisions

### What Makes a Good Test

- Test external behavior: given input PDF + config → expect correct output structure
- Don't test implementation details (internal function calls, singleton state, etc.)
- Use small test PDFs (1-3 pages) from `tests/unittest/pdfs/`

### Modules to Test

| Module | Test Type | Rationale |
|---|---|---|
| `mineru/client.py` | Integration | `MinerU.process()` with real PDF, verify `OCRResult` structure |
| `mineru/config.py` | Unit | Config builder, hierarchy, validation |
| `mineru/exceptions.py` | Unit | Exception hierarchy, string representation |
| `mineru/result.py` | Unit | Property access, data extraction |
| `mineru/cli/client.py` | Integration | CLI still works after refactoring (existing `test_e2e.py` covers this) |

### Prior Art

The existing `tests/unittest/test_e2e.py` runs end-to-end tests with the pipeline backend and both `txt` and `ocr` parse methods. New tests should follow the same pattern — process a test PDF and verify output files are created with correct structure.

### Test Matrix

| Backend | Parse Method | Device | Input Type |
|---|---|---|---|
| pipeline | auto | cpu | file path |
| pipeline | ocr | cpu | Path object |
| pipeline | txt | cpu | bytes |
| vlm-transformers | vlm | cpu | file path |

## Out of Scope

- Backend abstraction layer (Module 2)
- Additional OCR engines like Tesseract/EasyOCR (Module 3)
- Multiple VLM models (Module 4)
- Inference engine integrations (Module 5)
- Memory optimization and model unloading (Module 6)
- KV cache optimization (Module 7)
- Bulk job queue with Redis/Celery (Module 8)
- Docker improvements (Module 9)
- API server improvements (Module 10)
- Document processing pipeline (Module 11)
- Additional output formats (DOCX, EPUB, LaTeX) (Module 12)
- Test infrastructure overhaul (Module 13)
- Monitoring/observability (Module 14)
- Documentation website (Module 15)

## Further Notes

### Migration Path

This PRD is designed to be **non-breaking**. The existing CLI commands, environment variables, and config file format all continue to work. The new library API is additive — it sits on top of the existing infrastructure.

### Files to Create

| File | Purpose |
|---|---|
| `mineru/__init__.py` | Redefine public API exports |
| `mineru/client.py` | `MinerU` class (sync) |
| `mineru/async_client.py` | `AsyncMinerU` class (async) |
| `mineru/config.py` | `Config` builder |
| `mineru/exceptions.py` | Exception hierarchy |
| `mineru/result.py` | `OCRResult` structured result |
| `mineru/py.typed` | Type marker file |

### Files to Modify

| File | Change |
|---|---|
| `mineru/cli/client.py` | Use `MinerU` class instead of calling `do_parse()` directly |
| `pyproject.toml` | Add `py.typed`, classifiers |
| `mineru/data/utils/schemas.py` | Extend with `MinerUConfig` Pydantic model |
| `tests/unittest/test_e2e.py` | Add tests for new `MinerU` API |

### Implementation Order

1. `mineru/exceptions.py` — foundation, no dependencies
2. `mineru/config.py` — depends only on exceptions
3. `mineru/result.py` — depends only on existing middle JSON schema
4. `mineru/client.py` — depends on config, result, exceptions, and existing `do_parse()`
5. `mineru/async_client.py` — mirrors sync client
6. `mineru/__init__.py` — wire up all exports
7. `mineru/py.typed` — add marker file
8. `pyproject.toml` — add packaging config
9. `mineru/cli/client.py` — refactor to use `MinerU`
10. Tests — add test coverage for all new modules
