"""``edit``: change settings in one or many profiles, or reset them to inherit."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Any, TextIO

from orca_profiles.commands.base import Command, CommandError, add_type_option, pick_profile
from orca_profiles.core.editor import EditError, ProfileEdit, apply, plan
from orca_profiles.core.model import Origin, Profile
from orca_profiles.core.repository import ProfileRepository
from orca_profiles.core.resolver import build_chain


def _fmt(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _key_value(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key.strip():
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    return key.strip(), value


class EditCommand(Command):
    name = "edit"
    help = "change settings or reset them to inherit (preview unless --apply)"

    @classmethod
    def configure(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "profile", nargs="*", help="profile name (exact, or a unique substring)"
        )
        parser.add_argument(
            "-m",
            "--match",
            action="append",
            default=[],
            help="glob on profile name; selects every match (repeatable)",
        )
        add_type_option(parser)
        parser.add_argument(
            "--origin",
            type=Origin,
            choices=list(Origin),
            help="with --match: only user or only system profiles",
        )
        parser.add_argument(
            "--level",
            type=int,
            default=0,
            help="edit the Nth ancestor of each selected profile "
            "(0 = the profile itself, 1 = its parent, ...)",
        )
        parser.add_argument(
            "--set",
            dest="sets",
            type=_key_value,
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="set a value in the profile's own file",
        )
        parser.add_argument(
            "--inherit",
            action="append",
            default=[],
            metavar="KEY",
            help="remove the key from the profile so it is inherited",
        )
        parser.add_argument("--apply", action="store_true", help="write the changes")
        parser.add_argument(
            "--backup-dir",
            type=Path,
            help="where originals are copied (default ~/.orca-profiles/backups/<time>)",
        )

    def run(self, args: argparse.Namespace, repo: ProfileRepository, out: TextIO) -> int:
        if not args.sets and not args.inherit:
            raise CommandError("nothing to do: use --set KEY=VALUE and/or --inherit KEY")
        targets = self._targets(args, repo)
        try:
            edits = [plan(p, repo, dict(args.sets), args.inherit) for p in targets]
        except EditError as exc:
            raise CommandError(str(exc)) from exc
        changed = [e for e in edits if e.changes]
        for e in edits:
            self._render(e, out)
        if not changed:
            out.write("No changes.\n")
            return 0
        if not args.apply:
            out.write(
                f"\nPreview only: {len(changed)} profile(s) would change. "
                "Run again with --apply to write.\n"
            )
            return 0
        written = apply(changed, repo, args.backup_dir)
        out.write(f"\nWrote {len(written)} profile(s); originals backed up first.\n")
        for _, backup in written:
            out.write(f"  backup: {backup}\n")
        return 0

    @staticmethod
    def _targets(args: argparse.Namespace, repo: ProfileRepository) -> list[Profile]:
        selected = [pick_profile(repo, n, args.type) for n in args.profile]
        for pat in args.match:
            selected += [
                p
                for p in repo
                if fnmatch.fnmatchcase(p.name, pat)
                and (args.type is None or p.type is args.type)
                and (args.origin is None or p.origin is args.origin)
            ]
        if not selected:
            raise CommandError("no profiles selected: give a name or --match GLOB")
        targets: dict[str, Profile] = {}
        for p in selected:
            chain, _, _ = build_chain(p, repo)
            if args.level >= len(chain):
                raise CommandError(f"'{p.name}' has no ancestor at level {args.level}")
            t = chain[args.level]
            targets.setdefault(str(t.path), t)
        return list(targets.values())

    @staticmethod
    def _render(e: ProfileEdit, out: TextIO) -> None:
        p = e.profile
        out.write(f"\n{p.name}  [{p.type}, {p.origin}]  {p.path}\n")
        for w in e.warnings:
            out.write(f"  ! {w}\n")
        if not e.changes:
            out.write("  (no changes)\n")
        for c in e.changes:
            if c.is_inherit:
                src = (
                    f"inherit from {c.inherited_from}: {_fmt(c.inherited)}"
                    if c.inherited_from
                    else "no parent value"
                )
                out.write(f"  - {c.key}: {_fmt(c.old)}  ->  ({src})\n")
            else:
                old = "(inherited)" if c.old is None else _fmt(c.old)
                out.write(f"  ~ {c.key}: {old}  ->  {_fmt(c.new)}\n")
