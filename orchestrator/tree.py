"""In-memory tree structures used to organize descriptors."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Descriptor


@dataclass
class DescriptorTree:
    """Tree node containing descriptors and subfolders."""

    name: str
    parent: DescriptorTree | None = None
    descriptors: dict[str, Descriptor] = field(default_factory=dict)
    subfolders: dict[str, DescriptorTree] = field(default_factory=dict)

    def path(self) -> str:
        if self.parent is None:
            return "/"
        base = self.parent.path().rstrip("/")
        return f"{base}/{self.name}"


__all__ = ["DescriptorTree"]
