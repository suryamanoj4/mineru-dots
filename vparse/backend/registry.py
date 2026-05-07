from __future__ import annotations

import time
from typing import Any

from loguru import logger

from vparse.backend.base import BackendProtocol
from vparse.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from vparse.backend.hybrid.hybrid_analyze import aio_doc_analyze as hybrid_doc_analyze
from vparse.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from vparse.backend.lite.lite_analyze import doc_analyze as lite_doc_analyze
from vparse.backend.vlm.utils import resolve_vlm_engine
from vparse.data.data_reader_writer import DataWriter


class PipelineBackend:
    name = "pipeline"

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        middle_json, model_output = pipeline_doc_analyze(
            [pdf_bytes], [lang],
            parse_method=parse_method,
            formula_enable=formula_enable,
            table_enable=table_enable,
        )
        return middle_json, model_output

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def get_supported_languages(self) -> list[str]:
        return ["ch", "en", "korean", "japan", "th", "el", "latin", "arabic"]


class LiteBackend:
    name = "lite"

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        middle_json = lite_doc_analyze(
            pdf_bytes, image_writer=image_writer, lang=lang, **kwargs
        )
        return middle_json, {}

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def get_supported_languages(self) -> list[str]:
        return ["en", "ch"]


class VLMBackend:
    name = "vlm"

    def __init__(self):
        self._engine = None

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        engine = kwargs.pop("engine", self._resolve_engine())
        return await vlm_doc_analyze(
            pdf_bytes, image_writer=image_writer, backend=engine, **kwargs
        )

    def _resolve_engine(self) -> str:
        if self._engine:
            return self._engine
        self._engine = resolve_vlm_engine()
        return self._engine

    async def initialize(self) -> None:
        self._resolve_engine()

    async def shutdown(self) -> None:
        self._engine = None

    def is_available(self) -> bool:
        return True

    def get_supported_languages(self) -> list[str]:
        return ["ch", "en"]


class VLMLmdeployBackend(VLMBackend):
    name = "vlm-lmdeploy"

    def _resolve_engine(self) -> str:
        return "lmdeploy"


class HybridBackend:
    name = "hybrid"

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        middle_json, model_output, _ = await hybrid_doc_analyze(
            pdf_bytes,
            image_writer=image_writer,
            backend=kwargs.pop("engine", resolve_vlm_engine()),
            parse_method=parse_method,
            language=lang,
            inline_formula_enable=formula_enable,
            **kwargs,
        )
        return middle_json, model_output

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def get_supported_languages(self) -> list[str]:
        return ["ch", "en", "korean", "japan", "th", "el", "latin", "arabic"]


class HybridLmdeployBackend(HybridBackend):
    name = "hybrid-lmdeploy"

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        if "engine" not in kwargs:
            kwargs["engine"] = "lmdeploy"
        return await super().doc_analyze(
            pdf_bytes,
            lang=lang,
            parse_method=parse_method,
            formula_enable=formula_enable,
            table_enable=table_enable,
            image_writer=image_writer,
            **kwargs,
        )


class RemoteBackend:
    name = "remote"

    async def doc_analyze(
        self,
        pdf_bytes: bytes,
        lang: str = "en",
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writer: DataWriter | None = None,
        **kwargs,
    ) -> tuple[dict, dict]:
        server_url = kwargs.pop("server_url", None)
        return await vlm_doc_analyze(
            pdf_bytes,
            image_writer=image_writer,
            backend="vllm",
            server_url=server_url,
            **kwargs,
        )

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def get_supported_languages(self) -> list[str]:
        return ["ch", "en"]


class BackendRegistry:
    _backends: dict[str, type] = {}
    _instances: dict[str, BackendProtocol] = {}

    @classmethod
    def register(cls, backend_class: type) -> type:
        name = getattr(backend_class, "name", backend_class.__name__.lower())
        cls._backends[name] = backend_class
        return backend_class

    @classmethod
    def get(cls, name: str) -> BackendProtocol:
        name = _BACKEND_ALIASES.get(name, name)
        if name not in cls._instances:
            if name not in cls._backends:
                raise ValueError(
                    f"Unknown backend '{name}'. Available: {sorted(cls._backends)}"
                )
            cls._instances[name] = cls._backends[name]()
        return cls._instances[name]

    @classmethod
    def list_available(cls) -> dict[str, dict[str, Any]]:
        result = {}
        for name, backend_cls in cls._backends.items():
            try:
                instance = cls.get(name)
                result[name] = {
                    "available": instance.is_available(),
                    "languages": instance.get_supported_languages(),
                }
            except Exception:
                result[name] = {"available": False, "languages": []}
        return result

    @classmethod
    def get_backend_names(cls) -> list[str]:
        return sorted(cls._backends)


_BACKEND_ALIASES: dict[str, str] = {
    "vlm-auto-engine": "vlm",
    "vlm-vllm-engine": "vlm",
    "vlm-vllm-async-engine": "vlm",
    "vlm-dots-ocr-hf": "vlm",
    "vlm-dots-ocr-vllm": "vlm",
    "vlm-transformers": "vlm",
    "vlm-mlx-engine": "vlm",
    "vlm-lmdeploy-engine": "vlm-lmdeploy",
    "hybrid-auto-engine": "hybrid",
    "hybrid-vllm-engine": "hybrid",
    "hybrid-vllm-async-engine": "hybrid",
    "hybrid-lmdeploy-engine": "hybrid-lmdeploy",
    "hybrid-http-client": "hybrid",
    "vlm-http-client": "remote",
}


BackendRegistry.register(PipelineBackend)
BackendRegistry.register(LiteBackend)
BackendRegistry.register(VLMBackend)
BackendRegistry.register(VLMLmdeployBackend)
BackendRegistry.register(HybridBackend)
BackendRegistry.register(HybridLmdeployBackend)
BackendRegistry.register(RemoteBackend)
