# OrcaSlicer Profiles Bulk Editor

CLI tool to inspect (and, later, bulk-edit) OrcaSlicer profiles.

## Features

- `chain` – show the full `inherits` chain of a profile and, per setting, where the
  effective value comes from: `own` (override in the profile itself), `parent`
  (a user-created parent) or `system` (a vendor/system profile).
- `list` – list known profiles with their parent.

Planned: a compatibility matrix (profiles vs. printers/nozzles) and bulk editing.

## Install

```sh
pip install -e ".[dev]"
```

## Usage

By default the platform's OrcaSlicer data dir is used (`%APPDATA%\OrcaSlicer` on
Windows), which holds `system/` and `user/`.

```sh
orca-profiles chain "My PLA Silk"
orca-profiles chain "My PLA Silk" --source own            # only own overrides
orca-profiles chain "My PLA Silk" -k "nozzle_*" --history # incl. overridden values
orca-profiles chain "My PLA Silk" --format json
orca-profiles list --type filament --origin user PLA
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
  commands/      one module per feature, registered in commands/__init__.py
    chain.py, list.py
  cli.py         argparse entry point, loads the repository, dispatches commands
```

New features plug in as a `Command` subclass in `commands/`:

- **matrix** reads `compatible_printers` / `compatible_printers_condition` from
  `resolve(...).effective` and matches them against machine profiles in the repository.
- **bulk-edit** will add a writer to `core/` (edit a profile's own JSON, with dry-run and
  backups) and reuse the resolver to show what changes effectively.

## Development

```sh
pytest && ruff check . && ruff format --check . && mypy
```
