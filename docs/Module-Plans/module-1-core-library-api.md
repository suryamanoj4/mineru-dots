# Plan: Module 1 - Core Library & API Foundation

> Source PRD: `docs/Module-PRD/module-1-core-library-api.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Public API surface**: Only 17 symbols exported from `vparse/__init__.py` (VParse, AsyncVParse, Config, 7 exceptions, 3 result types, 4 data I/O types)
- **No backend refactoring**: This module wraps existing `do_parse()` / `aio_do_parse()` as-is. Backend abstraction is Module 2.
- **Config hierarchy**: defaults → file (~/.vparse.json) → env vars → programmatic `.set_*()` calls (later overrides earlier)
- **Non-breaking migration**: Existing CLI commands, env vars, and config file format must continue working exactly as before
- **Structured results**: `OCRResult` wraps the existing `middle_json` dict — it does not replace it
- **Context manager lifecycle**: `__enter__`/`__exit__` for resource cleanup (models, GPU memory)
- **Type hints required**: All public APIs must have type annotations; `py.typed` marker included
- **Pydantic for config/validation**: `Config` uses Pydantic internally; `PageInfo`, `BlockInfo` are Pydantic models

---

## Phase 1: Rebranding from MinerU to VParse

**Task**: Complete rebranding of the codebase from `mineru` to `vparse`

### What to build

Rename all references from `mineru` to `vparse` while maintaining full backward compatibility through aliases.

### Acceptance criteria

- [x] Package directory renamed: `mineru/` → `vparse/`
- [x] All Python imports updated: `import mineru` → `import vparse`
- [x] CLI entry points renamed: `mineru` → `vparse`, `mineru-api` → `vparse-api`, etc.
- [x] Old CLI commands (`mineru`, `mineru-api`, etc.) still work as aliases
- [x] Config file location: check `~/.mineru.json` if `~/.vparse.json` doesn't exist
- [x] Environment variables: `MINERU_*` → `VPARSE_*` (old ones still work)
- [x] pyproject.toml updated with new package name and entry points
- [x] Exception classes renamed: `MinerUError` → `VParseError`
- [x] All documentation updated
- [x] `from mineru import ...` still works via backward-compatible imports

---

## Phase 2: Exceptions + PyPI Packaging

**User stories**: #5 (exception hierarchy), #13 (PyPI installation)

### What to build

Create the exception hierarchy and update `pyproject.toml` so VParse can be installed from PyPI with proper type support. This is the foundation — zero dependencies, can be committed as the first atomic change.

### Acceptance criteria

- [x] `vparse/exceptions.py` created with full hierarchy (`VParseError` → `BackendError`, `ModelLoadError`, `ConfigurationError`, `InputError`, `ProcessingError`, `TimeoutError`)
- [x] `vparse/py.typed` marker file created
- [x] `pyproject.toml` updated with `[tool.setuptools.package-data]`, classifiers
- [x] Existing code in `vparse/data/utils/exceptions.py` updated to subclass from new `VParseError` (backward compatible)
- [x] `python -m build` succeeds in clean environment
- [x] No runtime behavior changes

---

## Phase 3: Config Builder + Result Object

**User stories**: #4 (fluent config), #9 (structured results), #6 (type hints — partial)

### What to build

Create `Config` fluent builder with Pydantic validation and `OCRResult` structured result wrapper. These are pure data-layer modules with no external dependencies — they can be tested in isolation.

### Acceptance criteria

- [ ] `vparse/config.py` created with `Config` class supporting fluent API (`set_backend()`, `set_device()`, `set_language()`, `enable_formula()`, etc.)
- [ ] Config hierarchy works: defaults < file < env < programmatic
- [ ] `vparse/result.py` created with `OCRResult`, `PageInfo`, `BlockInfo` classes
- [ ] `OCRResult.markdown()`, `OCRResult.content_list()`, `OCRResult.middle_json()` all return correct data
- [ ] Existing `vparse/utils/config_reader.py` functions (`get_device()`, `get_s3_config()`, etc.) still work (backward compatible)
- [ ] Unit tests for `Config` validation errors and `OCRResult` property access
- [ ] Full type hints on both modules

---

## Phase 4: Sync Client (VParse Class)

**User stories**: #1 (import VParse), #2 (context manager), #7 (output formats), #8 (input types), #10 (batch processing), #11 (available backends), #12 (progress callbacks)

### What to build

Create `VParse` class that wraps the existing `do_parse()` function. This is the core deliverable — a user can `from vparse import VParse` and process PDFs with one call.

### Acceptance criteria

- [ ] `vparse/client.py` created with `VParse` class
- [ ] `VParse.__init__()` accepts `backend`, `lang`, `device`, `config`, `output_format`, `formula_enable`, `table_enable`
- [ ] `VParse.process()` accepts file path, `Path`, or raw bytes; returns `OCRResult`
- [ ] `VParse.process_batch()` processes multiple files, returns `list[OCRResult]`
- [ ] Context manager works: `with VParse(...) as ocr:` cleans up on exit
- [ ] `VParse.get_available_backends()` returns `["pipeline", "vlm-auto-engine", "hybrid-auto-engine", ...]`
- [ ] Progress `callback(progress, total)` called during batch processing
- [ ] If `output_dir` is None, results written to temp directory
- [ ] Existing `do_parse()` function unchanged (backward compatible)
- [ ] Integration test: process a test PDF from `tests/unittest/pdfs/`, verify `OCRResult` structure
- [ ] Full type hints

---

## Phase 5: Async Client (AsyncVParse Class)

**User stories**: #3 (async client)

### What to build

Create `AsyncVParse` class that wraps the existing `aio_do_parse()` function. Mirrors the sync client API exactly.

### Acceptance criteria

- [ ] `vparse/async_client.py` created with `AsyncVParse` class
- [ ] `AsyncVParse.process()` is async, returns `OCRResult`
- [ ] `AsyncVParse.process_batch()` processes multiple files concurrently
- [ ] Async context manager works: `async with AsyncVParse(...) as ocr:`
- [ ] API signature matches `VParse` exactly (only `async` keyword differs)
- [ ] Existing `aio_do_parse()` function unchanged (backward compatible)
- [ ] Integration test with async processing of a test PDF
- [ ] Full type hints

---

## Phase 6: Public API Wiring + CLI Refactor + Tests

**User stories**: #6 (type hints — complete), #14 (CLI backward compatibility), all (library usability)

### What to build

Wire up `vparse/__init__.py` to export all public symbols. Refactor the existing CLI (`vparse/cli/client.py`) to use the new `VParse` class internally. Add full test coverage. This is the integration phase that makes everything work together.

### Acceptance criteria

- [ ] `vparse/__init__.py` exports all 17 public symbols defined in the PRD
- [ ] `vparse/cli/client.py` refactored to create `VParse` instance and call `process()` instead of calling `do_parse()` directly
- [ ] All existing CLI flags (`-p`, `-o`, `-m`, `-b`, `--formula-enable`, etc.) continue working (backward compatible)
- [ ] `vparse --version`, `vparse --help` output unchanged
- [ ] Existing `tests/unittest/test_e2e.py` still passes (regression test)
- [ ] New test file added covering: `VParse` process, `AsyncVParse` process, `Config` builder, `OCRResult` properties, exception handling
- [ ] Test matrix covers: pipeline/auto/cpu, pipeline/ocr/cpu, pipeline/txt/cpu
- [ ] `mypy --strict` passes on all 5 new public API files
- [ ] `pyproject.toml` includes all new files in package distribution

---

## Phase dependency graph

```
Phase 1: Rebranding VParse → VParse            (no dependencies)
    ↓
Phase 2: Exceptions + PyPI Packaging          (depends on Phase 1)
    ↓
Phase 3: Config Builder + Result Object        (depends on Phase 2 for exceptions)
    ↓
Phase 4: Sync Client (VParse)                  (depends on Phase 3 for Config + OCRResult)
    ↓
Phase 5: Async Client (AsyncVParse)            (depends on Phase 3 for Config + OCRResult, parallel with Phase 4)
    ↓
Phase 6: Public API Wiring + CLI Refactor      (depends on Phase 4 + Phase 5)
```

**Parallel opportunity**: Phase 4 and Phase 5 can be developed simultaneously since they both depend only on Phase 3.

## Implementation order

1. **Phase 1** — Rebranding (foundational, must be done first)
2. **Phase 2** — Exceptions + PyPI packaging (foundation after rebrand)
3. **Phase 3** — Data layer, fully testable in isolation
4. **Phase 4** — Core sync client (primary user-facing feature)
5. **Phase 5** — Async client (can be done in parallel with Phase 4)
6. **Phase 6** — Integration, CLI refactor, full test coverage
