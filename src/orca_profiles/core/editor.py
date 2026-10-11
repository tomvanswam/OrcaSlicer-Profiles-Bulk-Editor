"""Edit settings in profile files: set a value, or reset a setting to "inherit".

Any profile in a chain can be edited (the profile itself, a user parent or a system
profile). Setting a value writes it into that profile's own JSON; "inherit" removes the
key from that file so the value comes from the next ancestor again.

Edits are planned first (:func:`plan`) so callers can show a preview, then written with
:func:`apply`, which backs up every file before touching it.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from orca_profiles.core.model import META_KEYS, Origin, Profile
from orca_profiles.core.repository import ProfileRepository, load_profile
from orca_profiles.core.resolver import build_chain

INHERIT = object()
"""Sentinel value meaning "remove the key so it is inherited from the parent"."""


class EditError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Change:
    key: str
    old: Any  # ``None`` when the key was not defined in this file
    new: Any  # ``None`` when the key is removed (inherit)
    inherited: Any = None  # value the profile falls back to after an inherit
    inherited_from: str | None = None

    @property
    def is_inherit(self) -> bool:
        return self.new is None


@dataclass(slots=True)
class ProfileEdit:
    profile: Profile
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def new_data(self) -> dict[str, Any]:
        data = dict(self.profile.data)
        for c in self.changes:
            if c.is_inherit:
                data.pop(c.key, None)
            else:
                data[c.key] = c.new
        return data


def parse_value(text: str, current: Any) -> Any:
    """Turn user input into a value shaped like the current one.

    OrcaSlicer stores most settings as strings (``"220"``) or lists of strings
    (``["220"]``, one entry per extruder). A plain ``220`` for a list setting becomes
    ``["220"]``; a JSON list or object is taken as-is.
    """
    text = text.strip()
    if text.startswith(("[", "{")):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise EditError(f"invalid JSON value {text!r}: {exc}") from exc
    if isinstance(current, list):
        return [text]
    if isinstance(current, bool):
        return text.lower() in ("1", "true", "yes", "on")
    if isinstance(current, (int, float)):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _ancestor_value(profile: Profile, key: str, repo: ProfileRepository) -> tuple[Any, str | None]:
    chain, _, _ = build_chain(profile, repo)
    for p in chain[1:]:
        if key in p.settings:
            return p.settings[key], p.name
    return None, None


def plan(
    profile: Profile,
    repo: ProfileRepository,
    sets: Mapping[str, Any] | None = None,
    inherit: Iterable[str] = (),
) -> ProfileEdit:
    """Work out what changes in ``profile``'s own file. Values in ``sets`` that are
    strings are parsed with :func:`parse_value`; other values are used as-is."""
    edit = ProfileEdit(profile)
    if profile.origin is Origin.SYSTEM:
        edit.warnings.append(
            f"'{profile.name}' is a system profile: OrcaSlicer overwrites it on updates"
        )
    own = profile.settings
    set_keys: set[str] = set()
    for key, raw in (sets or {}).items():
        if key in META_KEYS:
            raise EditError(f"'{key}' describes the profile itself and cannot be edited here")
        current = own.get(key)
        if current is None:
            current, _ = _ancestor_value(profile, key, repo)
        value = parse_value(raw, current) if isinstance(raw, str) else raw
        set_keys.add(key)
        if key not in own or own[key] != value:
            edit.changes.append(Change(key, own.get(key), value))
    for key in inherit:
        if key in set_keys:
            raise EditError(f"'{key}' cannot be both set and inherited")
        if key not in own:
            continue  # already inherited
        value, source = _ancestor_value(profile, key, repo)
        if source is None:
            edit.warnings.append(
                f"'{key}' is not defined by any parent of '{profile.name}'; "
                "it will fall back to OrcaSlicer's built-in default"
            )
        edit.changes.append(Change(key, own[key], None, value, source))
    return edit


def _dump(data: Mapping[str, Any]) -> str:
    # OrcaSlicer writes presets with 4-space indentation.
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


def default_backup_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return Path.home() / ".orca-profiles" / "backups" / stamp


def apply(
    edits: Iterable[ProfileEdit], repo: ProfileRepository, backup_dir: Path | None = None
) -> list[tuple[Profile, Path]]:
    """Write the edits. Each original file is copied into ``backup_dir`` first.
    Returns ``(updated profile, backup path)`` pairs; ``repo`` is updated in place."""
    backup_dir = backup_dir or default_backup_dir()
    done: list[tuple[Profile, Path]] = []
    for edit in edits:
        if not edit.changes:
            continue
        src = edit.profile.path
        anchor = src.anchor.replace(":", "").strip("\\/")
        backup = backup_dir / anchor / src.relative_to(src.anchor)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, backup)
        tmp = src.with_suffix(src.suffix + ".tmp")
        tmp.write_text(_dump(edit.new_data()), encoding="utf-8")
        tmp.replace(src)
        updated = load_profile(src, edit.profile.origin, edit.profile.vendor)
        if updated is None:  # should not happen: name/type are never edited
            raise EditError(f"{src} is no longer a valid profile after editing")
        repo.replace(edit.profile, updated)
        done.append((updated, backup))
    return done
