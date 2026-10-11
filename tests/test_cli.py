import json
from pathlib import Path

import pytest

from orca_profiles.cli import main


def run(capsys: pytest.CaptureFixture[str], orca_dir: Path, *args: str) -> tuple[int, str, str]:
    code = main(["--orca-dir", str(orca_dir), *args])
    out, err = capsys.readouterr()
    return code, out, err


def test_chain_text(capsys: pytest.CaptureFixture[str], orca_dir: Path) -> None:
    code, out, _ = run(capsys, orca_dir, "chain", "My PLA Silk")
    assert code == 0
    assert "└─ My PLA base (user)" in out
    assert "fdm_filament_common (system, Acme)" in out
    assert "2 own, 1 parent, 2 system" in out


def test_chain_json_with_filters(capsys: pytest.CaptureFixture[str], orca_dir: Path) -> None:
    code, out, _ = run(capsys, orca_dir, "chain", "My PLA Silk", "--format", "json", "-s", "system")
    data = json.loads(out)
    assert code == 0
    assert set(data["settings"]) == {"compatible_printers", "filament_density"}
    assert data["settings"]["filament_density"]["from"] == "fdm_filament_common"


def test_chain_key_glob_and_history(capsys: pytest.CaptureFixture[str], orca_dir: Path) -> None:
    _, out, _ = run(capsys, orca_dir, "chain", "My PLA Silk", "-k", "nozzle_*", "--history")
    assert "nozzle_temperature" in out and "fan_max_speed" not in out
    assert out.count("↳") == 3


def test_ambiguous_and_unknown(capsys: pytest.CaptureFixture[str], orca_dir: Path) -> None:
    code, _, err = run(capsys, orca_dir, "chain", "PLA")
    assert code == 2 and "ambiguous" in err
    code, _, err = run(capsys, orca_dir, "chain", "nope")
    assert code == 2 and "no profile" in err


def test_list(capsys: pytest.CaptureFixture[str], orca_dir: Path) -> None:
    _, out, _ = run(capsys, orca_dir, "list", "--origin", "user")
    assert "My PLA Silk  <- My PLA base" in out and "Acme PLA" not in out.replace("<- Acme PLA", "")
