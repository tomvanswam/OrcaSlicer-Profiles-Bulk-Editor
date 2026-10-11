# OrcaSlicer Profiles Bulk Editor

CLI tool to inspect (and, later, bulk-edit) OrcaSlicer profiles.

## Features

- `chain` – show the full `inherits` chain of a profile and, per setting, where the
  effective value comes from: `own` (override in the profile itself), `parent`
  (a user-created parent) or `system` (a vendor/system profile).
- `list` – list known profiles with their parent.
- `edit` – change a setting, or reset it to *inherit* (remove the override so the value
  comes from the parent again), in any profile of the chain: the profile itself, a user
  parent or a system profile. Works on one profile or many (`--match`). Shows a preview
  by default; `--apply` writes, after copying each original file to
  `~/.orca-profiles/backups/<time>/`. Note: system profiles are overwritten when
  OrcaSlicer updates its profiles.
- `gui` – a graphical interface in your browser: search and filter profiles, see the
  chain as cards, and filter settings by source, by chain profile or by name. Runs
  fully locally (Python standard library only); press Ctrl+C to stop. Every setting row
  has an edit button (pick the chain level to change it in) and an inherit button;
  changes are collected, reviewed as a per-file diff and saved with backups.

Planned: a compatibility matrix (profiles vs. printers/nozzles).

## Install

```sh
pip install -e ".[dev]"
```

## Usage

By default the platform's OrcaSlicer data dir is used (`%APPDATA%\OrcaSlicer` on
Windows), which holds `system/` and `user/`.

```sh
orca-profiles gui
orca-profiles chain "My PLA Silk"
orca-profiles chain "My PLA Silk" --source own            # only own overrides
orca-profiles chain "My PLA Silk" -k "nozzle_*" --history # incl. overridden values
orca-profiles chain "My PLA Silk" --format json
orca-profiles list --type filament --origin user PLA
orca-profiles edit "My PLA Silk" --set nozzle_temperature=225     # preview
orca-profiles edit "My PLA Silk" --inherit fan_max_speed --apply  # write (with backup)
orca-profiles edit "My PLA Silk" --level 1 --set fan_max_speed=70 # edit its parent
orca-profiles edit -m "My PLA*" -t filament --origin user --inherit nozzle_temperature
orca-profiles --orca-dir D:\OrcaSlicer chain ...
orca-profiles --system-dir "C:\Program Files\OrcaSlicer\resources\profiles" chain ...
```

A `*` after the source marks a value that actually differs from the inherited one.

## Architecture

```
src/orca_profiles/
  core/          domain layer, no CLI knowledge
    model.py       Profile, ProfileType, Origin
    repository.py  discovers/indexes profile files, parent lookup
    resolver.py    builds the inherits chain and traces each setting
    editor.py      plan/apply setting changes and inherit resets, with backups
    serialize.py   JSON shapes shared by the CLI and the GUI API
  commands/      one module per feature, registered in commands/__init__.py
    chain.py, list.py, edit.py, gui.py
  gui/           local HTTP server (JSON API in ROUTES) + single-page UI in static/
  cli.py         argparse entry point, loads the repository, dispatches commands
```

New features plug in as a `Command` subclass in `commands/` and, for the GUI, an
endpoint in `gui/server.py:ROUTES` plus a view in the UI:

- **matrix** reads `compatible_printers` / `compatible_printers_condition` from
  `resolve(...).effective` and matches them against machine profiles in the repository.

## Development

```sh
pytest && ruff check . && ruff format --check . && mypy
```
