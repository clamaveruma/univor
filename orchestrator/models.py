"""Pydantic models that capture orchestrator domain concepts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import json
import yaml
from pydantic import BaseModel, Field, ValidationError


class LocalDefinition(BaseModel):
    """Base parameters defined at the descriptor level."""

    cpu: int = Field(..., ge=1, description="vCPU count")
    memory_mb: int = Field(..., ge=128, description="RAM in megabytes")
    tags: list[str] = Field(default_factory=list, description="Free-form labels")

    def merge(self, patch: Mapping[str, Any]) -> LocalDefinition:
        """Return a new LocalDefinition with ``patch`` applied."""
        payload = self.model_dump(mode="python")
        payload.update(patch)
        return LocalDefinition.model_validate(payload)


class Descriptor(BaseModel):
    """VM descriptor persisted by the orchestrator."""

    status: str = Field(default="provisioned")
    vm_id: str | None = None
    folder_path: str = Field(default="/", description="Path of the containing folder")
    name: str
    deployed_config: dict[str, Any] | None = None
    _local_definition: LocalDefinition = Field(alias="local_definition")

    def __init__(self, **data: Any) -> None:
        raw_definition = data.pop("local_definition", data.pop("_local_definition", None))
        super().__init__(
            **data,
            _local_definition=coerce_local_definition(raw_definition) if raw_definition is not None else None,
        )

    @property
    def local_definition(self) -> LocalDefinition:
        return self._local_definition

    @local_definition.setter
    def local_definition(self, value: Any) -> None:
        self._local_definition = coerce_local_definition(value)

    @property
    def full_name(self) -> str:
        base = self.folder_path.rstrip("/")
        if not base:
            base = "/"
        if base == "/":
            return f"/{self.name}".replace("//", "/")
        return f"{base}/{self.name}".replace("//", "/")

    def with_local_definition(self, value: Any) -> Descriptor:
        """Return a copy of this descriptor with a normalized local definition."""
        normalized = coerce_local_definition(value)
        clone = self.model_copy(deep=True)
        clone.local_definition = normalized
        return clone

    def merge_local_definition(self, patch: Mapping[str, Any]) -> Descriptor:
        """Return a new descriptor with ``patch`` merged into the local definition."""
        merged = self.local_definition.merge(patch)
        clone = self.model_copy(deep=True)
        clone.local_definition = merged
        return clone
# ---------------------------------------------------------------------------
# helpers


def coerce_local_definition(value: Any) -> LocalDefinition:
    """Normalize supported inputs into a LocalDefinition instance."""
    if isinstance(value, LocalDefinition):
        return value
    payload: Mapping[str, Any]
    if isinstance(value, Mapping):
        payload = value
    elif isinstance(value, (str, bytes)):
        payload = _load_text_payload(value)
    elif isinstance(value, Path):
        payload = _load_text_payload(value.read_text())
    else:
        raise TypeError("Unsupported value for local_definition assignment")
    try:
        return LocalDefinition.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Invalid local_definition payload") from exc


def _load_text_payload(raw: str | bytes) -> dict[str, Any]:
    """Interpret raw text as YAML first, falling back to JSON."""
    text = raw.decode() if isinstance(raw, bytes) else raw
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return json.loads(text)


__all__ = [
    "Descriptor",
    "LocalDefinition",
    "coerce_local_definition",
]
