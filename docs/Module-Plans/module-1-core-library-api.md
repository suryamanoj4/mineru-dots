# Plan: Module 1 - Core Library & API Foundation

> Source PRD: `docs/Module-PRD/module-1-core-library-api.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Public API surface**: Only 17 symbols exported from `mineru/__init__.py` (MinerU, AsyncMinerU, Config, 7 exceptions, 3 result types, 4 data I/O types)
- **No backend refactoring**: This module wraps existing `do_parse()` / `aio_do_parse()` as-is. Backend abstraction is Module 2.
- **Config hierarchy**: defaults → file (~/.mineru.json) → env vars → programmatic `.set_*()` calls (later overrides earlier)
- **Non-breaking migration**: Existing CLI commands, env vars, and config file format must continue working exactly as before
- **Structured results**: `OCRResult` wraps the existing `middle_json` dict — it does not replace it
- **Context manager lifecycle**: `__enter__`/`__exit__` for resource cleanup (models, GPU memory)
- **Type hints required**: All public APIs must have type annotations; `py.typed` marker included
- **Pydantic for config/validation**: `Config` uses Pydantic internally; `PageInfo`, `BlockInfo` are Pydantic models

---

## Phase 1: Exceptions + PyPI Packaging

**User stories**: #5 (exception hierarchy), #13 (PyPI installation)

### What to build

Create the exception hierarchy and update `pyproject.toml` so MinerU can be installed from PyPI with proper type support. This is the foundation — zero dependencies, can be committed as the first atomic change.

### Acceptance criteria

- [ ] `mineru/exceptions.py` created with full hierarchy (`MinerUError` → `BackendError`, `ModelLoadError`, `ConfigurationError`, `InputError`, `ProcessingError`, `TimeoutError`)
- [ ] `mineru/py.typed` marker file created
- [ ] `pyproject.toml` updated with `[tool.setuptools.package-data]`, classifiers
- [ ] Existing code in `mineru/data/utils/exceptions.py` updated to subclass from new `MinerUError` (backward compatible)
- [ ] `python -m build` succeeds in clean environment
- [ ] No runtime behavior changes

---

## Phase 2: Config Builder + Result Object

**User stories**: #4 (fluent config), #9 (structured results), #6 (type hints — partial)

### What to build

Create `Config` fluent builder with Pydantic validation and `OCRResult` structured result wrapper. These are pure data-layer modules with no external dependencies — they can be tested in isolation.

### Acceptance criteria

- [ ] `mineru/config.py` created with `Config` class supporting fluent API (`set_backend()`, `set_device()`, `set_language()`, `enable_formula()`, etc.)
- [ ] Config hierarchy works: defaults < file < env < programmatic
- [ ] `mineru/result.py` created with `OCRResult`, `PageInfo`, `BlockInfo` classes
- [ ] `OCRResult.markdown()`, `OCRResult.content_list()`, `OCRResult.middle_json()` all return correct data
- [ ] Existing `mineru/utils/config_reader.py` functions (`get_device()`, `get_s3_config()`, etc.) still work (backward compatible)
- [ ] Unit tests for `Config` validation errors and `OCRResult` property access
- [ ] Full type hints on both modules

---

## Phase 3: Sync Client (MinerU Class)

**User stories**: #1 (import MinerU), #2 (context manager), #7 (output formats), #8 (input types), #10 (batch processing), #11 (available backends), #12 (progress callbacks)

### What to build

Create `MinerU` class that wraps the existing `do_parse()` function. This is the core deliverable — a user can `from mineru import MinerU` and process PDFs with one call.

### Acceptance criteria

- [ ] `mineru/client.py` created with `MinerU` class
- [ ] `MinerU.__init__()` accepts `backend`, `lang`, `device`, `config`, `output_format`, `formula_enable`, `table_enable`
- [ ] `MinerU.process()` accepts file path, `Path`, or raw bytes; returns `OCRResult`
- [ ] `MinerU.process_batch()` processes multiple files, returns `list[OCRResult]`
- [ ] Context manager works: `with MinerU(...) as ocr:` cleans up on exit
- [ ] `MinerU.get_available_backends()` returns `["pipeline", "vlm-auto-engine", "hybrid-auto-engine", ...]`
- [ ] Progress `callback(progress, total)` called during batch processing
- [ ] If `output_dir` is None, results written to temp directory
- [ ] Existing `do_parse()` function unchanged (backward compatible)
- [ ] Integration test: process a test PDF from `tests/unittest/pdfs/`, verify `OCRResult` structure
- [ ] Full type hints

---

## Phase 4: Async Client (AsyncMinerU Class)

**User stories**: #3 (async client)

### What to build

Create `AsyncMinerU` class that wraps the existing `aio_do_parse()` function. Mirrors the sync client API exactly.

### Acceptance criteria

- [ ] `mineru/async_client.py` created with `AsyncMinerU` class
- [ ] `AsyncMinerU.process()` is async, returns `OCRResult`
- [ ] `AsyncMinerU.process_batch()` processes multiple files concurrently
- [ ] Async context manager works: `async with AsyncMinerU(...) as ocr:`
- [ ] API signature matches `MinerU` exactly (only `async` keyword differs)
- [ ] Existing `aio_do_parse()` function unchanged (backward compatible)
- [ ] Integration test with async processing of a test PDF
- [ ] Full type hints

---

## Phase 5: Public API Wiring + CLI Refactor + Tests

**User stories**: #6 (type hints — complete), #14 (CLI backward compatibility), all (library usability)

### What to build

Wire up `mineru/__init__.py` to export all public symbols. Refactor the existing CLI (`mineru/cli/client.py`) to use the new `MinerU` class internally. Add full test coverage. This is the integration phase that makes everything work together.

### Acceptance criteria

- [ ] `mineru/__init__.py` exports all 17 public symbols defined in the PRD
- [ ] `mineru/cli/client.py` refactored to create `MinerU` instance and call `process()` instead of calling `do_parse()` directly
- [ ] All existing CLI flags (`-p`, `-o`, `-m`, `-b`, `--formula-enable`, etc.) continue working (backward compatible)
- [ ] `mineru --version`, `mineru --help` output unchanged
- [ ] Existing `tests/unittest/test_e2e.py` still passes (regression test)
- [ ] New test file added covering: `MinerU` process, `AsyncMinerU` process, `Config` builder, `OCRResult` properties, exception handling
- [ ] Test matrix covers: pipeline/auto/cpu, pipeline/ocr/cpu, pipeline/txt/cpu
- [ ] `mypy --strict` passes on all 5 new public API files
- [ ] `pyproject.toml` includes all new files in package distribution

---

## Phase dependency graph

```
Phase 1: Exceptions + PyPI Packaging          (no dependencies)
    ↓
Phase 2: Config Builder + Result Object        (depends on Phase 1 for exceptions)
    ↓
Phase 3: Sync Client (MinerU)                  (depends on Phase 2 for Config + OCRResult)
    ↓
Phase 4: Async Client (AsyncMinerU)            (depends on Phase 2 for Config + OCRResult, parallel with Phase 3)
    ↓
Phase 5: Public API Wiring + CLI Refactor      (depends on Phase 3 + Phase 4)
```

**Parallel opportunity**: Phase 3 and Phase 4 can be developed simultaneously since they both depend only on Phase 2.

## Implementation order

1. **Phase 1** — Foundation, zero dependencies, can ship immediately
2. **Phase 2** — Data layer, fully testable in isolation
3. **Phase 3** — Core sync client (primary user-facing feature)
4. **Phase 4** — Async client (can be done in parallel with Phase 3)
5. **Phase 5** — Integration, CLI refactor, full test coverage
