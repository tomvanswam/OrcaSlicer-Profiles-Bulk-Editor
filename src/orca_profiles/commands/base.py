from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import ClassVar, TextIO

from orca_profiles.core.model import Profile, ProfileType
from orca_profiles.core.repository import ProfileRepository


class CommandError(Exception):
    """A user-facing error; printed without a traceback."""


class Command(ABC):
    name: ClassVar[str]
    help: ClassVar[str]

    @classmethod
    @abstractmethod
    def configure(cls, parser: argparse.ArgumentParser) -> None: ...

    @abstractmethod
    def run(self, args: argparse.Namespace, repo: ProfileRepository, out: TextIO) -> int: ...


def add_type_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-t", "--type", type=ProfileType, choices=list(ProfileType), help="profile type"
    )


def pick_profile(repo: ProfileRepository, name: str, ptype: ProfileType | None) -> Profile:
    """Find exactly one profile by exact name, falling back to a unique substring match."""
    matches = repo.find(name, ptype) or repo.search(name, ptype)
    if not matches:
        raise CommandError(f"no profile matches '{name}'")
    if len(matches) > 1:
        lines = "\n".join(f"  [{p.type}] {p.name}  ({p.origin}, {p.path})" for p in matches[:20])
        more = f"\n  ... and {len(matches) - 20} more" if len(matches) > 20 else ""
        raise CommandError(
            f"'{name}' is ambiguous ({len(matches)} matches); use the exact name or --type:\n"
            f"{lines}{more}"
        )
    return matches[0]
