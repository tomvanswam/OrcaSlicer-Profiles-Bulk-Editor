"""JSON-friendly representations of domain objects, shared by CLI output and the GUI API."""

from __future__ import annotations

from typing import Any

from orca_profiles.core.editor import ProfileEdit
from orca_profiles.core.model import Profile
from orca_profiles.core.resolver import ResolvedProfile, ResolvedSetting


def profile_ref(p: Profile) -> dict[str, Any]:
    return {
        "name": p.name,
        "type": p.type,
        "origin": p.origin,
        "vendor": p.vendor,
        "inherits": p.inherits,
        "path": str(p.path),
    }


def resolved_to_json(
    r: ResolvedProfile, settings: list[ResolvedSetting] | None = None
) -> dict[str, Any]:
    chosen = list(r.settings.values()) if settings is None else settings
    return {
        "profile": profile_ref(r.profile),
        "chain": [profile_ref(p) | {"own_settings": len(p.settings)} for p in r.chain],
        "warnings": r.warnings,
        "settings": {
            s.key: {
                "value": s.value,
                "source": s.kind,
                "from": s.source.name,
                "differs": s.is_override,
                "overrides": [{"from": p.name, "value": v} for p, v in s.shadowed],
            }
            for s in chosen
        },
    }


def edit_to_json(e: ProfileEdit) -> dict[str, Any]:
    return {
        "profile": profile_ref(e.profile),
        "warnings": e.warnings,
        "changes": [
            {
                "key": c.key,
                "old": c.old,
                "new": c.new,
                "inherit": c.is_inherit,
                "inherited": c.inherited,
                "inherited_from": c.inherited_from,
            }
            for c in e.changes
        ],
    }
