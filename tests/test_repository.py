from orca_profiles.core import Origin, ProfileRepository, ProfileType


def test_loads_presets_and_skips_non_presets(repo: ProfileRepository) -> None:
    names = {p.name for p in repo}
    assert names == {
        "fdm_filament_common",
        "Acme PLA",
        "Acme X1 0.4 nozzle",
        "My PLA base",
        "My PLA Silk",
        "Orphan",
    }
    assert len(repo.errors) == 1 and "broken.json" in repo.errors[0]


def test_type_origin_and_vendor(repo: ProfileRepository) -> None:
    [base] = repo.find("My PLA base")
    assert base.type is ProfileType.FILAMENT  # inferred from the dir above ``base/``
    assert base.origin is Origin.USER and base.vendor is None
    [pla] = repo.find("Acme PLA")
    assert pla.origin is Origin.SYSTEM and pla.vendor == "Acme"
    [common] = repo.find("fdm_filament_common")
    assert not common.is_instantiable


def test_parent_prefers_user_profile_for_user_child(repo: ProfileRepository) -> None:
    [silk] = repo.find("My PLA Silk")
    parent = repo.parent_of(silk)
    assert parent is not None and parent.name == "My PLA base"


def test_portable_install_dir(tmp_path, orca_dir) -> None:  # type: ignore[no-untyped-def]
    import shutil

    shutil.copytree(orca_dir, tmp_path / "datadir")
    assert len(ProfileRepository.from_orca_dir(tmp_path)) == 6
