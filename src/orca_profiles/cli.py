"""Command-line entry point."""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from orca_profiles import __version__
from orca_profiles.commands import COMMANDS
from orca_profiles.commands.base import Command, CommandError
from orca_profiles.core.model import Origin
from orca_profiles.core.repository import ProfileRepository


def default_orca_dir() -> Path:
    """The OrcaSlicer data directory for the current platform."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "OrcaSlicer"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/OrcaSlicer"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "OrcaSlicer"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orca-profiles", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--orca-dir",
        type=Path,
        help="OrcaSlicer data dir containing system/ and user/ (default: platform location)",
    )
    parser.add_argument(
        "--system-dir",
        type=Path,
        action="append",
        default=[],
        help="extra system profile tree, e.g. <OrcaSlicer install>/resources/profiles",
    )
    parser.add_argument(
        "--user-dir", type=Path, action="append", default=[], help="extra user profile tree"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for cmd in COMMANDS:
        cmd.configure(sub.add_parser(cmd.name, help=cmd.help, description=cmd.help))
        sub.choices[cmd.name].set_defaults(command_cls=cmd)
    return parser


def load_repository(args: argparse.Namespace) -> ProfileRepository:
    explicit = bool(args.system_dir or args.user_dir)
    orca_dir = args.orca_dir or (None if explicit else default_orca_dir())
    repo = ProfileRepository.from_orca_dir(orca_dir) if orca_dir else ProfileRepository()
    for d in args.system_dir:
        repo.load_tree(d, Origin.SYSTEM)
    for d in args.user_dir:
        repo.load_tree(d, Origin.USER)
    if not len(repo):
        raise CommandError(
            f"no profiles found (looked in {orca_dir or 'the given directories'}); "
            "use --orca-dir, --system-dir or --user-dir"
        )
    return repo


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.ERROR, format="%(levelname)s: %(message)s"
    )
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        repo = load_repository(args)
        command: Command = args.command_cls()
        return command.run(args, repo, sys.stdout)
    except CommandError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
