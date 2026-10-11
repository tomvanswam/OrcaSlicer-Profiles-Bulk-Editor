"""``chain``: show the full inherits chain of a profile and where every setting comes from."""

from __future__ import annotations

import argparse
import fnmatch
import json
from typing import Any, TextIO

from orca_profiles.commands.base import Command, add_type_option, pick_profile
from orca_profiles.core.model import Profile
from orca_profiles.core.repository import ProfileRepository
from orca_profiles.core.resolver import ResolvedProfile, ResolvedSetting, SourceKind, resolve


def _fmt(value: Any, width: int = 40) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= width else text[: width - 1] + "…"


def _label(p: Profile) -> str:
    return f"{p.name} ({p.origin}{', ' + p.vendor if p.vendor else ''})"


class ChainCommand(Command):
    name = "chain"
    help = "show the inherits chain of a profile and the origin of every setting"

    @classmethod
    def configure(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("profile", help="profile name (exact, or a unique substring)")
        add_type_option(parser)
        parser.add_argument(
            "-s",
            "--source",
            type=SourceKind,
            choices=list(SourceKind),
            action="append",
            help="only show settings from this source (repeatable)",
        )
        parser.add_argument("-k", "--key", action="append", help="glob filter on setting key")
        parser.add_argument(
            "--history", action="store_true", help="also show the values each setting overrides"
        )
        parser.add_argument("--format", choices=["text", "json"], default="text")

    def run(self, args: argparse.Namespace, repo: ProfileRepository, out: TextIO) -> int:
        resolved = resolve(pick_profile(repo, args.profile, args.type), repo)
        settings = [s for s in resolved.settings.values() if self._keep(s, args)]
        if args.format == "json":
            json.dump(self._to_json(resolved, settings), out, indent=2, ensure_ascii=False)
            out.write("\n")
        else:
            self._render_text(resolved, settings, args.history, out)
        return 0

    @staticmethod
    def _keep(s: ResolvedSetting, args: argparse.Namespace) -> bool:
        if args.source and s.kind not in args.source:
            return False
        return not args.key or any(fnmatch.fnmatch(s.key, pat) for pat in args.key)

    @staticmethod
    def _render_text(
        r: ResolvedProfile, settings: list[ResolvedSetting], history: bool, out: TextIO
    ) -> None:
        out.write(f"Profile: {r.profile.name}  [{r.profile.type}]\n")
        out.write(f"File:    {r.profile.path}\n\nInherits chain:\n")
        for depth, p in enumerate(r.chain):
            out.write(
                f"  {'  ' * depth}{'└─ ' if depth else ''}{_label(p)}  "
                f"[{len(p.settings)} settings]\n"
            )
        for w in r.warnings:
            out.write(f"  ! {w}\n")

        counts = {k: sum(1 for s in r.settings.values() if s.kind is k) for k in SourceKind}
        out.write(
            "\nSettings: "
            + ", ".join(f"{counts[k]} {k}" for k in SourceKind)
            + f" (showing {len(settings)})\n\n"
        )
        if not settings:
            return
        kw = max(len(s.key) for s in settings)
        out.write(f"{'KEY':<{kw}}  {'SOURCE':<6}  {'VALUE':<40}  FROM\n")
        for s in settings:
            from_ = "" if s.kind is SourceKind.OWN else s.source.name
            mark = "*" if s.is_override else " "
            out.write(f"{s.key:<{kw}}  {s.kind:<6}{mark} {_fmt(s.value):<40}  {from_}\n")
            if history:
                for p, v in s.shadowed:
                    out.write(f"{'':<{kw}}  {'':<6}  ↳ {_fmt(v):<38}  {p.name}\n")
        out.write("\n* = differs from the inherited value\n")

    @staticmethod
    def _to_json(r: ResolvedProfile, settings: list[ResolvedSetting]) -> dict[str, Any]:
        def ref(p: Profile) -> dict[str, Any]:
            return {"name": p.name, "origin": p.origin, "vendor": p.vendor, "path": str(p.path)}

        return {
            "profile": ref(r.profile) | {"type": r.profile.type},
            "chain": [ref(p) for p in r.chain],
            "warnings": r.warnings,
            "settings": {
                s.key: {
                    "value": s.value,
                    "source": s.kind,
                    "from": s.source.name,
                    "overrides": [{"from": p.name, "value": v} for p, v in s.shadowed],
                }
                for s in settings
            },
        }
