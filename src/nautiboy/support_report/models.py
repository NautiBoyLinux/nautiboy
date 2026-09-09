"""Immutable models for passive hardware support reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    schema_version: int
    generated_utc: str
    privacy: dict[str, Any]
    host: dict[str, Any]
    devices: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
