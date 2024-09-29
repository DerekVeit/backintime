from collections.abc import Generator
from pathlib import Path

import pytest

import config
import snapshots
import tools


@pytest.fixture
def bit_config(tmp_path: Path) -> Generator[config.Config, None, None]:
    config_path = (Path(__file__) / "../config").resolve()
    data_path = tmp_path / "data"

    bit_config = config.Config(
        str(config_path),  # config file at backintime/common/test/config
        str(data_path),  # real default would be ~/.local/share
    )  # type: ignore[no-untyped-call]

    snapshots_path = tmp_path / "snapshots"
    snapshots_path.mkdir()
    bit_config.set_snapshots_path(str(snapshots_path))  # type: ignore[no-untyped-call]
    tools.validate_and_prepare_snapshots_path(
        path=snapshots_path,
        host_user_profile=bit_config.hostUserProfile(),  # type: ignore[no-untyped-call]
        mode=bit_config.snapshotsMode(),  # type: ignore[no-untyped-call]
        copy_links=bit_config.copyLinks(),  # type: ignore[no-untyped-call]
        error_handler=bit_config.notifyError,
    )

    bit_config.SELECTIONS_MODE = "sorted"  # type: ignore[attr-defined]

    yield bit_config


@pytest.fixture
def bit_snapshot(
    bit_config: config.Config,
) -> Generator[snapshots.Snapshots, None, None]:
    yield snapshots.Snapshots(bit_config)  # type: ignore[no-untyped-call]
