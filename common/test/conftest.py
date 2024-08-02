import pathlib

import pytest

import config
import snapshots


@pytest.fixture
def bit_config(tmp_path):
    config_path = (pathlib.Path(__file__) / "../config").resolve()
    data_path = tmp_path / "data"
    bit_config = config.Config(
        str(config_path),   # config file at backintime/common/test/config
        str(data_path),     # real default would be ~/.local/share
    )

    snapshots_path = tmp_path / "snapshots"
    snapshots_path.mkdir()
    bit_config.setSnapshotsPath(str(snapshots_path))

    bit_config.SELECTIONS_MODE = "sorted"

    yield bit_config


@pytest.fixture
def bit_snapshot(bit_config):
    yield snapshots.Snapshots(bit_config)
