from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .exceptions import ConfigurationError, InputError, ProcessingError
from .result import OCRResult
from .utils.enum_class import MakeMode
from .version import __version__


_AVAILABLE_BACKENDS = [
    "pipeline",
    "lite",
    "vlm-http-client",
    "hybrid-http-client",
    "vlm-auto-engine",
    "hybrid-auto-engine",
]
_SUPPORTED_METHODS = {"auto", "txt", "ocr"}
_SUPPORTED_OUTPUT_FORMATS = {
    MakeMode.MM_MD,
    MakeMode.NLP_MD,
    MakeMode.CONTENT_LIST,
}
_CTOR_DEFAULTS = {
    "backend": "pipeline",
    "lang": "en",
    "output_format": MakeMode.MM_MD,
    "formula_enable": True,
    "table_enable": True,
}


def _guess_input_suffix(file_bytes: bytes) -> str:
    from vparse.utils.guess_suffix_or_lang import guess_suffix_by_bytes

    return guess_suffix_by_bytes(file_bytes)


def _convert_image_bytes_to_pdf(file_bytes: bytes) -> bytes:
    from vparse.utils.pdf_image_tools import images_bytes_to_pdf_bytes

    return images_bytes_to_pdf_bytes(file_bytes)


def _cleanup_device_memory(device: str | None) -> None:
    if not device:
        return

    try:
        from vparse.utils.model_utils import clean_memory
    except Exception:
        return

    try:
        clean_memory(device)
    except Exception:
        return


class VParse:
    """High-level synchronous OCR processor built on top of ``do_parse()``."""

    def __init__(
        self,
        backend: str = "pipeline",
        lang: str = "en",
        device: str | None = None,
        config: Config | None = None,
        output_format: str = MakeMode.MM_MD,
        formula_enable: bool = True,
        table_enable: bool = True,
        **kwargs: Any,
    ) -> None:
        resolved = self._resolve_config(
            backend=backend,
            lang=lang,
            device=device,
            config=config,
            output_format=output_format,
            formula_enable=formula_enable,
            table_enable=table_enable,
        )

        self.backend: str = resolved["backend"]
        self.lang: str = resolved["lang"]
        self.device: str | None = resolved["device"]
        self.output_format: str = resolved["output_format"]
        self.formula_enable: bool = resolved["formula_enable"]
        self.table_enable: bool = resolved["table_enable"]
        self._resolved_config = resolved
        self._default_parse_kwargs = dict(kwargs)
        self._owned_temp_dirs: set[Path] = set()

    @staticmethod
    def _extract_config_overrides(config: Config) -> dict[str, Any]:
        built = config.build()
        overrides = built.model_dump(exclude_defaults=True)
        programmatic_overrides = getattr(config, "_programmatic_overrides", None)
        if isinstance(programmatic_overrides, dict):
            overrides.update(programmatic_overrides)
        return overrides

    @classmethod
    def _resolve_config(
        cls,
        *,
        backend: str,
        lang: str,
        device: str | None,
        config: Config | None,
        output_format: str,
        formula_enable: bool,
        table_enable: bool,
    ) -> dict[str, Any]:
        if config is not None and not isinstance(config, Config):
            raise ConfigurationError("config must be an instance of Config")

        resolved = Config().load_from_file().load_from_env().to_dict()

        if config is not None:
            resolved.update(cls._extract_config_overrides(config))

        explicit_values = {
            "backend": backend,
            "lang": lang,
            "output_format": output_format,
            "formula_enable": formula_enable,
            "table_enable": table_enable,
        }
        for key, value in explicit_values.items():
            if value != _CTOR_DEFAULTS[key]:
                resolved[key] = value

        if device is not None:
            resolved["device"] = device

        normalized_output_format = resolved.get("output_format", MakeMode.MM_MD)
        if normalized_output_format not in _SUPPORTED_OUTPUT_FORMATS:
            raise ConfigurationError(
                "output_format must be one of "
                f"{sorted(_SUPPORTED_OUTPUT_FORMATS)}"
            )
        resolved["output_format"] = normalized_output_format

        backend_name = resolved.get("backend", "pipeline")
        if backend_name not in _AVAILABLE_BACKENDS:
            raise ConfigurationError(
                f"backend must be one of {sorted(_AVAILABLE_BACKENDS)}"
            )

        return resolved

    def _normalize_method(self, method: str) -> str:
        if method not in _SUPPORTED_METHODS:
            raise InputError(
                f"Unsupported method '{method}'. Expected one of {sorted(_SUPPORTED_METHODS)}"
            )
        return method

    def _ensure_output_root(self, output_dir: str | Path | None) -> Path:
        if output_dir is None:
            temp_root = Path(tempfile.mkdtemp(prefix="vparse-"))
            self._owned_temp_dirs.add(temp_root)
            return temp_root

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        return output_root

    def _discard_temp_root(self, output_root: Path) -> None:
        if output_root in self._owned_temp_dirs:
            self._owned_temp_dirs.remove(output_root)
            shutil.rmtree(output_root, ignore_errors=True)

    def _default_markdown_mode(self) -> str:
        if self.output_format in (MakeMode.MM_MD, MakeMode.NLP_MD):
            return self.output_format
        return MakeMode.MM_MD

    def _make_md_mode(self) -> str:
        return self._default_markdown_mode()

    def _resolve_parse_subdir(self, method: str) -> str:
        if self.backend in {"pipeline", "lite"}:
            from vparse.cli.common import get_pipeline_subdir

            return get_pipeline_subdir(self.backend, method)
        if self.backend.startswith("vlm-"):
            return "vlm"
        if self.backend.startswith("hybrid-"):
            return f"hybrid_{method}"
        return method

    def _normalize_input(
        self,
        input_path: str | Path | bytes,
        default_name: str,
    ) -> tuple[str, bytes]:
        from vparse.cli.common import image_suffixes, pdf_suffixes, read_fn

        if isinstance(input_path, (str, Path)):
            source_path = Path(input_path)
            if not source_path.exists():
                raise InputError(f"Input path does not exist: {source_path}")
            try:
                return source_path.stem or default_name, read_fn(source_path)
            except Exception as exc:
                raise InputError(f"Failed to read input '{source_path}': {exc}") from exc

        if isinstance(input_path, (bytes, bytearray)):
            raw_bytes = bytes(input_path)
            try:
                suffix = _guess_input_suffix(raw_bytes)
            except Exception as exc:
                raise InputError(f"Failed to detect input type from bytes: {exc}") from exc

            if suffix in pdf_suffixes:
                return default_name, raw_bytes
            if suffix in image_suffixes:
                try:
                    return default_name, _convert_image_bytes_to_pdf(raw_bytes)
                except Exception as exc:
                    raise InputError(
                        f"Failed to convert image bytes to PDF bytes: {exc}"
                    ) from exc

            raise InputError(f"Unsupported input bytes type: {suffix}")

        raise InputError(
            "input_path must be a filesystem path, Path object, or raw bytes"
        )

    def _read_result(
        self,
        output_root: Path,
        pdf_file_name: str,
        method: str,
        dump_middle_json: bool,
    ) -> OCRResult:
        parse_dir = output_root / pdf_file_name / self._resolve_parse_subdir(method)
        middle_json_path = parse_dir / f"{pdf_file_name}_middle.json"
        if not middle_json_path.exists():
            raise ProcessingError(
                f"Expected result file was not created: {middle_json_path}"
            )

        try:
            with open(middle_json_path, "r", encoding="utf-8") as handle:
                middle_json = json.load(handle)
        except Exception as exc:
            raise ProcessingError(
                f"Failed to load result JSON from {middle_json_path}: {exc}"
            ) from exc

        if not dump_middle_json:
            middle_json_path.unlink(missing_ok=True)

        return OCRResult(
            middle_json,
            output_dir=parse_dir,
            default_markdown_mode=self._default_markdown_mode(),
        )

    def _run_parse(
        self,
        *,
        output_root: Path,
        pdf_file_name: str,
        pdf_bytes: bytes,
        method: str,
        draw_layout_bbox: bool,
        draw_span_bbox: bool,
        dump_md: bool,
        dump_content_list: bool,
        dump_middle_json: bool,
        dump_model_output: bool,
        dump_orig_pdf: bool,
    ) -> OCRResult:
        from vparse.cli.common import do_parse, temporary_env

        parse_kwargs = dict(self._default_parse_kwargs)
        env_updates: dict[str, str] = {}
        if self.device is not None:
            env_updates["VPARSE_DEVICE_MODE"] = self.device
            env_updates["MINERU_DEVICE_MODE"] = self.device

        try:
            with temporary_env(**env_updates):
                do_parse(
                    output_dir=str(output_root),
                    pdf_file_names=[pdf_file_name],
                    pdf_bytes_list=[pdf_bytes],
                    p_lang_list=[self.lang],
                    backend=self.backend,
                    parse_method=method,
                    formula_enable=self.formula_enable,
                    table_enable=self.table_enable,
                    f_draw_layout_bbox=draw_layout_bbox,
                    f_draw_span_bbox=draw_span_bbox,
                    f_dump_md=dump_md,
                    f_dump_content_list=dump_content_list,
                    f_dump_middle_json=True,
                    f_dump_model_output=dump_model_output,
                    f_dump_orig_pdf=dump_orig_pdf,
                    f_make_md_mode=self._make_md_mode(),
                    **parse_kwargs,
                )
        except (InputError, ConfigurationError, ProcessingError):
            raise
        except Exception as exc:
            raise ProcessingError(
                f"Failed to process '{pdf_file_name}' with backend '{self.backend}': {exc}"
            ) from exc

        return self._read_result(output_root, pdf_file_name, method, dump_middle_json)

    def _unique_name(self, base_name: str, used_names: set[str]) -> str:
        candidate = base_name or "document"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

        suffix = 2
        while True:
            deduped = f"{candidate}_{suffix}"
            if deduped not in used_names:
                used_names.add(deduped)
                return deduped
            suffix += 1

    def process(
        self,
        input_path: str | Path | bytes,
        output_dir: str | Path | None = None,
        method: str = "auto",
        draw_layout_bbox: bool = False,
        draw_span_bbox: bool = False,
        dump_md: bool = True,
        dump_content_list: bool = False,
        dump_middle_json: bool = False,
        dump_model_output: bool = False,
        dump_orig_pdf: bool = False,
        callback: Callable[[int, int], None] | None = None,
    ) -> OCRResult:
        normalized_method = self._normalize_method(method)
        output_root = self._ensure_output_root(output_dir)

        try:
            pdf_file_name, pdf_bytes = self._normalize_input(input_path, "document")
            result = self._run_parse(
                output_root=output_root,
                pdf_file_name=pdf_file_name,
                pdf_bytes=pdf_bytes,
                method=normalized_method,
                draw_layout_bbox=draw_layout_bbox,
                draw_span_bbox=draw_span_bbox,
                dump_md=dump_md,
                dump_content_list=dump_content_list,
                dump_middle_json=dump_middle_json,
                dump_model_output=dump_model_output,
                dump_orig_pdf=dump_orig_pdf,
            )
        except Exception:
            if output_dir is None:
                self._discard_temp_root(output_root)
            raise

        if callback is not None:
            callback(1, 1)

        return result

    def process_batch(
        self,
        input_paths: list[str | Path | bytes],
        output_dir: str | Path | None = None,
        method: str = "auto",
        draw_layout_bbox: bool = False,
        draw_span_bbox: bool = False,
        dump_md: bool = True,
        dump_content_list: bool = False,
        dump_middle_json: bool = False,
        dump_model_output: bool = False,
        dump_orig_pdf: bool = False,
        callback: Callable[[int, int], None] | None = None,
    ) -> list[OCRResult]:
        normalized_method = self._normalize_method(method)
        output_root = self._ensure_output_root(output_dir)
        try:
            total = len(input_paths)
            used_names: set[str] = set()
            results: list[OCRResult] = []

            for index, input_path in enumerate(input_paths, start=1):
                base_name = "document"
                if isinstance(input_path, (str, Path)):
                    path_name = Path(input_path).stem
                    if path_name:
                        base_name = path_name
                pdf_file_name = self._unique_name(base_name, used_names)
                _, pdf_bytes = self._normalize_input(input_path, pdf_file_name)
                result = self._run_parse(
                    output_root=output_root,
                    pdf_file_name=pdf_file_name,
                    pdf_bytes=pdf_bytes,
                    method=normalized_method,
                    draw_layout_bbox=draw_layout_bbox,
                    draw_span_bbox=draw_span_bbox,
                    dump_md=dump_md,
                    dump_content_list=dump_content_list,
                    dump_middle_json=dump_middle_json,
                    dump_model_output=dump_model_output,
                    dump_orig_pdf=dump_orig_pdf,
                )
                results.append(result)

                if callback is not None:
                    callback(index, total)

            return results
        except Exception:
            if output_dir is None:
                self._discard_temp_root(output_root)
            raise

    def get_available_backends(self) -> list[str]:
        return list(_AVAILABLE_BACKENDS)

    def get_version(self) -> str:
        return __version__

    def cleanup(self) -> None:
        for temp_root in list(self._owned_temp_dirs):
            shutil.rmtree(temp_root, ignore_errors=True)
            self._owned_temp_dirs.discard(temp_root)
        _cleanup_device_memory(self.device)

    def __enter__(self) -> "VParse":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
