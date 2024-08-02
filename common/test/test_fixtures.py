import config
import snapshots

from test.logging import log


def test_config(bit_config):
    log(f"{bit_config._LOCAL_MOUNT_ROOT = }")
    assert isinstance(bit_config, config.Config)
    excludes = bit_config.exclude()
    assert ".Private" in excludes
    assert "/home/derek/Local" not in excludes


def test_snapshot(bit_snapshot):
    log(f"{bit_snapshot.config._LOCAL_MOUNT_ROOT = }")
    assert isinstance(bit_snapshot, snapshots.Snapshots)
