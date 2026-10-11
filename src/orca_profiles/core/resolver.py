"""Resolve the ``inherits`` chain of a profile and trace each setting to its origin."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from orca_profiles.core.model import Origin, Profile
from orca_profiles.core.repository import ProfileRepository


class SourceKind(StrEnum):
    OWN = "own"  # defined in the profile itself (override)
    PARENT = "parent"  # inherited from a user-created parent
    SYSTEM = "system"  # inherited from a system/vendor profile


@dataclass(frozen=True, slots=True)
class ResolvedSetting:
    key: str
    value: Any
    source: Profile
    kind: SourceKind
    # Values this setting replaced further up the chain, nearest ancestor first.
    shadowed: tuple[tuple[Profile, Any], ...] = ()

    @property
    def is_override(self) -> bool:
        """True when this value differs from what the ancestors would have provided."""
        return bool(self.shadowed) and self.shadowed[0][1] != self.value


@dataclass(frozen=True, slots=True)
class ResolvedProfile:
    profile: Profile
    chain: tuple[Profile, ...]  # profile first, root ancestor last
    settings: dict[str, ResolvedSetting]
    missing_parent: str | None = None  # name of an ``inherits`` target that was not found
    cycle: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def effective(self) -> dict[str, Any]:
        return {k: s.value for k, s in self.settings.items()}


def build_chain(
    profile: Profile, repo: ProfileRepository
) -> tuple[list[Profile], str | None, bool]:
    chain = [profile]
    seen = {id(profile)}
    current = profile
    while current.inherits is not None:
        parent = repo.parent_of(current)
        if parent is None:
            return chain, current.inherits, False
        if id(parent) in seen:
            return chain, None, True
        chain.append(parent)
        seen.add(id(parent))
        current = parent
    return chain, None, False


def _kind(source: Profile, profile: Profile) -> SourceKind:
    if source is profile:
        return SourceKind.OWN
    return SourceKind.SYSTEM if source.origin is Origin.SYSTEM else SourceKind.PARENT


def resolve(profile: Profile, repo: ProfileRepository) -> ResolvedProfile:
    chain, missing, cycle = build_chain(profile, repo)
    settings: dict[str, ResolvedSetting] = {}
    for key in {k for p in chain for k in p.settings}:
        defined = [(p, p.settings[key]) for p in chain if key in p.settings]
        source, value = defined[0]
        settings[key] = ResolvedSetting(
            key=key,
            value=value,
            source=source,
            kind=_kind(source, profile),
            shadowed=tuple(defined[1:]),
        )
    warnings = []
    if missing:
        warnings.append(f"parent profile '{missing}' not found; chain is incomplete")
    if cycle:
        warnings.append("inheritance cycle detected; chain was cut")
    return ResolvedProfile(
        profile=profile,
        chain=tuple(chain),
        settings=dict(sorted(settings.items())),
        missing_parent=missing,
        cycle=cycle,
        warnings=warnings,
    )
