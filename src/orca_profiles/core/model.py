"""Domain model for OrcaSlicer profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# Keys that describe the profile itself rather than a slicer setting.
META_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "inherits",
        "from",
        "type",
        "instantiation",
        "setting_id",
        "filament_id",
        "version",
        "is_custom_defined",
        "base_id",
        "user_id",
        "updated_time",
        "description",
    }
)


class ProfileType(StrEnum):
    MACHINE = "machine"
    FILAMENT = "filament"
    PROCESS = "process"


class Origin(StrEnum):
    """Where a profile file lives: shipped by OrcaSlicer/vendor, or created by the user."""

    SYSTEM = "system"
    USER = "user"


@dataclass(frozen=True, slots=True)
class Profile:
    """A single profile JSON file, exactly as stored on disk (no inheritance applied)."""

    name: str
    type: ProfileType
    origin: Origin
    path: Path
    data: Mapping[str, Any] = field(repr=False)
    vendor: str | None = None

    @property
    def inherits(self) -> str | None:
        parent = self.data.get("inherits")
        return parent if isinstance(parent, str) and parent else None

    @property
    def settings(self) -> dict[str, Any]:
        """The settings this file defines itself, without metadata keys."""
        return {k: v for k, v in self.data.items() if k not in META_KEYS}

    @property
    def is_instantiable(self) -> bool:
        """System base profiles (``instantiation: false``) are hidden templates in the UI."""
        return str(self.data.get("instantiation", "true")).lower() != "false"
