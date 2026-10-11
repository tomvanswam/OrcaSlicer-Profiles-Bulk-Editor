from pathlib import Path

import pytest

from orca_profiles.core import ProfileRepository

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "orca"


@pytest.fixture
def orca_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture
def repo(orca_dir: Path) -> ProfileRepository:
    return ProfileRepository.from_orca_dir(orca_dir)
