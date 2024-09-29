from pathlib import Path

import pytest

import config
import snapshots
import tools


@pytest.fixture
def bit_config(tmp_path):
    config_path = (Path(__file__) / "../config").resolve()
    data_path = tmp_path / "data"

    bit_config = config.Config(
        str(config_path),   # config file at backintime/common/test/config
        str(data_path),     # real default would be ~/.local/share
    )

    snapshots_path = tmp_path / "snapshots"
    snapshots_path.mkdir()
    bit_config.set_snapshots_path(str(snapshots_path))
    tools.validate_and_prepare_snapshots_path(
        path=snapshots_path,
        host_user_profile=bit_config.hostUserProfile(),
        mode=bit_config.snapshotsMode(),
        copy_links=bit_config.copyLinks(),
        error_handler=bit_config.notifyError)

    bit_config.SELECTIONS_MODE = "sorted"

    yield bit_config


@pytest.fixture
def bit_snapshot(bit_config):
    yield snapshots.Snapshots(bit_config)
