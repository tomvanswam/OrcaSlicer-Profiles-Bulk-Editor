"""``gui``: open the graphical interface in the default web browser."""

from __future__ import annotations

import argparse
import webbrowser
from typing import TextIO

from orca_profiles.commands.base import Command
from orca_profiles.core.repository import ProfileRepository
from orca_profiles.gui.server import create_server


class GuiCommand(Command):
    name = "gui"
    help = "open the graphical interface in your browser"

    @classmethod
    def configure(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=0, help="default: a free port")
        parser.add_argument("--no-browser", action="store_true", help="don't open a browser")

    def run(self, args: argparse.Namespace, repo: ProfileRepository, out: TextIO) -> int:
        server = create_server(repo, args.host, args.port)
        host, port = server.server_address[:2]
        url = f"http://{host!s}:{port}/"
        out.write(f"OrcaSlicer profiles GUI on {url}  ({len(repo)} profiles; Ctrl+C to stop)\n")
        out.flush()
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
