"""CLI sub-commands. Each feature lives in its own module and registers a :class:`Command`.

To add a feature (e.g. ``matrix`` or ``bulk-edit``): create a module with a ``Command``
subclass and append it to :data:`COMMANDS`.
"""

from orca_profiles.commands.base import Command
from orca_profiles.commands.chain import ChainCommand
from orca_profiles.commands.list import ListCommand

COMMANDS: tuple[type[Command], ...] = (ListCommand, ChainCommand)

__all__ = ["COMMANDS", "Command"]
