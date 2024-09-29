import config
import snapshots

from test.logging import log

"""
This module contains tests for the fixtures defined in conftest.py.
"""


def test_config(bit_config: config.Config) -> None:
    """Test the bit_config fixture."""
    log(f"{bit_config._LOCAL_MOUNT_ROOT = }")
    assert isinstance(bit_config, config.Config)
    excludes = bit_config.exclude()  # type: ignore[no-untyped-call]
    assert ".Private" in excludes
    assert "/home/derek/Local" not in excludes


def test_snapshot(bit_snapshot: snapshots.Snapshots) -> None:
    """Test the bit_snapshot fixture."""
    log(f"{bit_snapshot.config._LOCAL_MOUNT_ROOT = }")
    assert isinstance(bit_snapshot, snapshots.Snapshots)
