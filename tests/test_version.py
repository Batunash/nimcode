"""Tests for __version__ single source of truth."""
import pytest


def test_version_format():
    """Version should be a valid semver string."""
    from nimcode.__version__ import __version__
    parts = __version__.split(".")
    assert len(parts) == 3, f"Version should be x.y.z, got {__version__}"
    for part in parts:
        assert part.isdigit(), f"Version part '{part}' is not a digit"


def test_version_is_0_4_4():
    """Current version should be 0.4.4."""
    from nimcode.__version__ import __version__
    assert __version__ == "0.4.4"


def test_updater_uses_version():
    """updater.py should use the same version as __version__.py."""
    from nimcode.__version__ import __version__
    from nimcode.updater import CURRENT_VERSION
    assert CURRENT_VERSION == __version__
