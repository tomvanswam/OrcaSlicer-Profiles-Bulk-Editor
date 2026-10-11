from __future__ import annotations

import argparse
from typing import TextIO

from orca_profiles.commands.base import Command, add_type_option
from orca_profiles.core.model import Origin
from orca_profiles.core.repository import ProfileRepository


class ListCommand(Command):
    name = "list"
    help = "list known profiles"

    @classmethod
    def configure(cls, parser: argparse.ArgumentParser) -> None:
        add_type_option(parser)
        parser.add_argument("--origin", type=Origin, choices=list(Origin))
        parser.add_argument("filter", nargs="?", help="case-insensitive substring of the name")

    def run(self, args: argparse.Namespace, repo: ProfileRepository, out: TextIO) -> int:
        profiles = repo.search(args.filter or "", args.type)
        if args.origin:
            profiles = [p for p in profiles if p.origin is args.origin]
        for p in sorted(profiles, key=lambda p: (p.type, p.origin, p.name)):
            parent = f"  <- {p.inherits}" if p.inherits else ""
            out.write(f"[{p.type:<8}] [{p.origin:<6}] {p.name}{parent}\n")
        return 0
