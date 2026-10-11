"""Core domain layer: profile model, loading and inheritance resolution.

This layer knows nothing about the CLI. Feature commands (chain viewer, compatibility
matrix, bulk editing) are built on top of it in :mod:`orca_profiles.commands`.
"""

from orca_profiles.core.model import Origin, Profile, ProfileType
from orca_profiles.core.repository import ProfileRepository
from orca_profiles.core.resolver import ResolvedProfile, ResolvedSetting, SourceKind, resolve

__all__ = [
    "Origin",
    "Profile",
    "ProfileRepository",
    "ProfileType",
    "ResolvedProfile",
    "ResolvedSetting",
    "SourceKind",
    "resolve",
]
