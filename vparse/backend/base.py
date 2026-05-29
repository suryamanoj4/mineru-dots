from __future__ import annotations

from typing import Protocol, runtime_checkable

from vparse.data.data_reader_writer import DataWriter


@runtime_checkable
class BackendProtocol(Protocol):
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
        ...

    async def batch_analyze(
        self,
        pdf_bytes_list: list[bytes],
        langs: list[str] | None = None,
        parse_method: str = "auto",
        formula_enable: bool = True,
        table_enable: bool = True,
        image_writers: list[DataWriter | None] | None = None,
        **kwargs,
    ) -> list[tuple[dict, dict]]:
        ...

    async def initialize(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...

    def is_available(self) -> bool:
        ...

    def get_supported_languages(self) -> list[str]:
        ...
