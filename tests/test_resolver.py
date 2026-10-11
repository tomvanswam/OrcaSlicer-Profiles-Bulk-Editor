from orca_profiles.core import ProfileRepository, SourceKind, resolve


def test_chain_and_sources(repo: ProfileRepository) -> None:
    [silk] = repo.find("My PLA Silk")
    r = resolve(silk, repo)
    assert [p.name for p in r.chain] == [
        "My PLA Silk",
        "My PLA base",
        "Acme PLA",
        "fdm_filament_common",
    ]
    s = r.settings
    assert s["nozzle_temperature"].kind is SourceKind.OWN
    assert s["nozzle_temperature"].value == ["225"]
    assert [p.name for p, _ in s["nozzle_temperature"].shadowed] == [
        "My PLA base",
        "Acme PLA",
        "fdm_filament_common",
    ]
    assert s["fan_max_speed"].kind is SourceKind.PARENT
    assert s["compatible_printers"].kind is SourceKind.SYSTEM
    assert s["filament_density"].source.name == "fdm_filament_common"
    assert "name" not in s and "inherits" not in s
    assert r.effective["filament_flow_ratio"] == ["0.95"]


def test_redundant_override_is_not_flagged(repo: ProfileRepository) -> None:
    [base] = repo.find("My PLA base")
    temp = resolve(base, repo).settings["nozzle_temperature"]
    assert temp.kind is SourceKind.OWN and not temp.is_override


def test_missing_parent(repo: ProfileRepository) -> None:
    [orphan] = repo.find("Orphan")
    r = resolve(orphan, repo)
    assert r.missing_parent == "Does Not Exist" and len(r.chain) == 1 and r.warnings


def test_cycle_is_cut() -> None:
    from pathlib import Path

    from orca_profiles.core import Origin, Profile, ProfileType

    def mk(name: str, parent: str) -> Profile:
        return Profile(
            name,
            ProfileType.PROCESS,
            Origin.USER,
            Path(name),
            {"name": name, "inherits": parent, "x": name},
        )

    repo = ProfileRepository([mk("a", "b"), mk("b", "a")])
    r = resolve(repo.find("a")[0], repo)
    assert r.cycle and [p.name for p in r.chain] == ["a", "b"]
