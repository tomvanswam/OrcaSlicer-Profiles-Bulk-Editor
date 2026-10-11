import json
import shutil
from pathlib import Path

import pytest

from orca_profiles.cli import main
from orca_profiles.core import ProfileRepository, resolve
from orca_profiles.core.editor import EditError, apply, parse_value, plan


@pytest.fixture
def work_dir(orca_dir: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "orca"
    shutil.copytree(orca_dir, dst)
    return dst


@pytest.fixture
def wrepo(work_dir: Path) -> ProfileRepository:
    return ProfileRepository.from_orca_dir(work_dir)


def test_parse_value_follows_existing_shape() -> None:
    assert parse_value("220", ["210"]) == ["220"]
    assert parse_value("220", "210") == "220"
    assert parse_value('["1", "2"]', ["0"]) == ["1", "2"]
    with pytest.raises(EditError):
        parse_value("[oops", None)


def test_set_and_inherit_at_every_level(wrepo: ProfileRepository, tmp_path: Path) -> None:
    [silk] = wrepo.find("My PLA Silk")
    [base] = wrepo.find("My PLA base")
    [common] = wrepo.find("fdm_filament_common")
    edits = [
        plan(silk, wrepo, inherit=["nozzle_temperature"]),
        plan(base, wrepo, {"filament_density": "1.3"}),
        plan(common, wrepo, {"fan_max_speed": "90"}),
    ]
    assert edits[0].changes[0].inherited == ["210"]
    assert edits[0].changes[0].inherited_from == "My PLA base"
    assert edits[1].changes[0].new == ["1.3"] and edits[1].changes[0].old is None
    assert "system profile" in edits[2].warnings[0]

    written = apply(edits, wrepo, tmp_path / "bak")
    assert len(written) == 3 and all(b.is_file() for _, b in written)

    [silk] = wrepo.find("My PLA Silk")
    r = resolve(silk, wrepo)
    assert "nozzle_temperature" not in silk.data
    assert r.settings["nozzle_temperature"].source.name == "My PLA base"
    assert r.effective["filament_density"] == ["1.3"]
    assert json.loads(common.path.read_text())["fan_max_speed"] == ["90"]
    # backups hold the original content
    backup = next(b for p, b in written if p.name == "My PLA Silk")
    assert json.loads(backup.read_text())["nozzle_temperature"] == ["225"]


def test_noop_and_errors(wrepo: ProfileRepository) -> None:
    [silk] = wrepo.find("My PLA Silk")
    assert not plan(silk, wrepo, {"nozzle_temperature": "225"}, ["fan_max_speed"]).changes
    with pytest.raises(EditError):
        plan(silk, wrepo, {"inherits": "x"})
    with pytest.raises(EditError):
        plan(silk, wrepo, {"a": "1"}, ["a"])
    [common] = wrepo.find("fdm_filament_common")
    warnings = plan(common, wrepo, inherit=["fan_max_speed"]).warnings
    assert "not defined by any parent" in warnings[-1]


def test_cli_preview_then_apply(
    capsys: pytest.CaptureFixture[str], work_dir: Path, tmp_path: Path
) -> None:
    silk = work_dir / "user/default/filament/My PLA Silk.json"
    before = silk.read_text()
    args = [
        "--orca-dir",
        str(work_dir),
        "edit",
        "My PLA Silk",
        "--level",
        "1",
        "--set",
        "fan_max_speed=70",
        "--backup-dir",
        str(tmp_path / "b"),
    ]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "My PLA base" in out and "Preview only" in out
    base = work_dir / "user/default/filament/base/My PLA base.json"
    assert json.loads(base.read_text())["fan_max_speed"] == ["80"]

    assert main([*args, "--apply"]) == 0
    assert json.loads(base.read_text())["fan_max_speed"] == ["70"]
    assert silk.read_text() == before


def test_cli_bulk_match(capsys: pytest.CaptureFixture[str], work_dir: Path) -> None:
    code = main(
        [
            "--orca-dir",
            str(work_dir),
            "edit",
            "-m",
            "My PLA*",
            "-t",
            "filament",
            "--inherit",
            "nozzle_temperature",
            "--apply",
            "--backup-dir",
            str(work_dir / "b"),
        ]
    )
    assert code == 0
    for name in ("My PLA Silk", "base/My PLA base"):
        data = json.loads((work_dir / f"user/default/filament/{name}.json").read_text())
        assert "nozzle_temperature" not in data
