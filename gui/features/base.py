"""Structural interface for adding a conversion feature."""
from typing import Any, Protocol
from pathlib import Path


class ConversionResult(Protocol):
    warnings: list[str]
    image_count: int


class ConversionFeature(Protocol):
    key: str
    title: str
    icon_name: str
    extensions: tuple[str, ...]
    file_filter: str
    select_label: str
    preview_label: str
    open_label: str
    output_hint: str
    settings_label: str | None

    def create_options(self, parent: Any) -> Any: ...
    def read_options(self, widget: Any) -> dict: ...
    def convert(self, source: Path, output: str | None, overwrite: bool, settings: dict, log: Any) -> ConversionResult: ...
    def preview_path(self, result: Any) -> Path: ...
    def result_path(self, result: Any) -> Path: ...
