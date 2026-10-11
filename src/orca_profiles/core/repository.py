"""Discovering and indexing profile files on disk."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from orca_profiles.core.model import Origin, Profile, ProfileType

log = logging.getLogger(__name__)


class ProfileLoadError(Exception):
    pass


def load_profile(path: Path, origin: Origin, vendor: str | None = None) -> Profile | None:
    """Load one JSON file. Returns ``None`` for JSON files that are not presets
    (e.g. vendor index files such as ``BBL.json``)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileLoadError(f"{path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        return None

    type_hint = data.get("type") or path.parent.name
    # User presets are sometimes stored in a ``base`` subdirectory.
    if type_hint == "base":
        type_hint = path.parent.parent.name
    try:
        ptype = ProfileType(type_hint)
    except ValueError:
        return None
    return Profile(
        name=data["name"], type=ptype, origin=origin, path=path, data=data, vendor=vendor
    )


class ProfileRepository:
    """In-memory index of all known profiles, keyed by type and name.

    Lookup rules mirror OrcaSlicer: a parent is searched among profiles of the same type;
    a system profile prefers a parent from its own vendor, a user profile prefers another
    user profile before falling back to system profiles.
    """

    def __init__(self, profiles: Iterable[Profile] = ()) -> None:
        self._profiles: list[Profile] = []
        self._by_key: dict[tuple[ProfileType, str], list[Profile]] = defaultdict(list)
        self.errors: list[str] = []
        for profile in profiles:
            self.add(profile)

    # -- building -----------------------------------------------------------------------

    def add(self, profile: Profile) -> None:
        self._profiles.append(profile)
        self._by_key[(profile.type, profile.name)].append(profile)

    def replace(self, old: Profile, new: Profile) -> None:
        """Swap a profile for a re-loaded version of the same file."""
        self._profiles[next(i for i, p in enumerate(self._profiles) if p is old)] = new
        bucket = self._by_key[(old.type, old.name)]
        bucket[next(i for i, p in enumerate(bucket) if p is old)] = new

    def find_by_path(self, path: str | Path) -> Profile | None:
        return next((p for p in self._profiles if str(p.path) == str(path)), None)

    def load_tree(self, root: Path, origin: Origin) -> None:
        """Load every preset below ``root``.

        For system trees the first directory level below ``root`` is taken as the vendor
        (``system/<Vendor>/filament/x.json`` or ``resources/profiles/<Vendor>/...``).
        """
        for path in sorted(root.rglob("*.json")):
            vendor = None
            if origin is Origin.SYSTEM:
                rel = path.relative_to(root).parts
                if len(rel) < 3:  # vendor index files live directly under root
                    continue
                vendor = rel[0]
            try:
                profile = load_profile(path, origin, vendor)
            except ProfileLoadError as exc:
                log.warning("Skipping unreadable profile: %s", exc)
                self.errors.append(str(exc))
                continue
            if profile is not None:
                self.add(profile)

    @classmethod
    def from_orca_dir(cls, orca_dir: Path) -> ProfileRepository:
        """Build a repository from an OrcaSlicer data dir (``%APPDATA%/OrcaSlicer``),
        which contains ``system/`` and ``user/`` subdirectories."""
        repo = cls()
        # A portable install keeps its data in a subfolder of the install dir.
        if not (orca_dir / "system").is_dir():
            for sub in ("datadir", "data_dir"):
                if (orca_dir / sub / "system").is_dir():
                    orca_dir = orca_dir / sub
                    break
        if (orca_dir / "system").is_dir():
            repo.load_tree(orca_dir / "system", Origin.SYSTEM)
        if (orca_dir / "user").is_dir():
            repo.load_tree(orca_dir / "user", Origin.USER)
        return repo

    # -- querying -----------------------------------------------------------------------

    def __iter__(self) -> Iterator[Profile]:
        return iter(self._profiles)

    def __len__(self) -> int:
        return len(self._profiles)

    def find(self, name: str, ptype: ProfileType | None = None) -> list[Profile]:
        types = [ptype] if ptype else list(ProfileType)
        return [p for t in types for p in self._by_key.get((t, name), [])]

    def search(self, needle: str, ptype: ProfileType | None = None) -> list[Profile]:
        needle = needle.casefold()
        return [
            p
            for p in self._profiles
            if needle in p.name.casefold() and (ptype is None or p.type is ptype)
        ]

    def parent_of(self, profile: Profile) -> Profile | None:
        if profile.inherits is None:
            return None
        candidates = self._by_key.get((profile.type, profile.inherits), [])
        if not candidates:
            return None

        def rank(c: Profile) -> tuple[int, int]:
            if profile.origin is Origin.USER:
                return (0 if c.origin is Origin.USER else 1, 0)
            same_vendor = c.vendor == profile.vendor
            return (0 if c.origin is Origin.SYSTEM else 1, 0 if same_vendor else 1)

        best = min((c for c in candidates if c is not profile), key=rank, default=None)
        return best
