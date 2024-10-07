from collections.abc import Generator
import ddt
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Union
import unittest

import config
import snapshots
import tools

from test import filetree
from test.logging import log


@ddt.ddt
class RsyncSuffixTests(unittest.TestCase):
    """Test the rsyncSuffix function."""

    @ddt.file_data('selection_cases.yaml')
    def test_rsyncSuffix__original(self, **kwargs: Any) -> None:
        self.assert_backup('original', **kwargs)

    @ddt.file_data('selection_cases.yaml')
    def test_rsyncSuffix__sorted(self, **kwargs: Any) -> None:
        self.assert_backup('sorted', **kwargs)

    def assert_backup(
        self,
        selections_mode: str,
        includes: list[str],
        excludes: list[str],
        files_tree: str,
        expected_tree: str,
        flags: Union[list[str], None] = None,
    ) -> None:
        """Verify that running `Snapshots.backup` copies the right files.

        Args:
            selections_mode: "original" or "sorted"
            includes: The list of included paths.
            excludes: The list of excluded paths.
            files_tree: The tree of files available to the backup.
            expected_tree: The tree of files expected in the backup.
            original_fails: Whether the test is expected to fail with the
                original strategy.
        """
        if flags is None:
            flags = []

        files_tree = filetree.normal(files_tree)
        expected_tree = filetree.normal(expected_tree)

        if selections_mode == 'original' and 'original_fails' in flags:
            self.skipTest('expected to fail with original strategy')
        elif selections_mode != 'sorted' and 'sorted_only' in flags:
            self.skipTest('only applicable for the sorted strategy')

        temp_dir = get_temp_dir(self)
        bit_config = get_bit_config(temp_dir)
        bit_snapshot = snapshots.Snapshots(bit_config)  # type: ignore[no-untyped-call]

        if 'fs_root' in flags:
            files_root = Path("/")
        else:
            files_root = temp_dir / 'files'
            files_root.mkdir()
            includes = list(prepend_paths(files_root, includes))
            excludes = list(prepend_paths(files_root, excludes))
            filetree.files_from_tree(files_root, files_tree)

        update_config(bit_config, includes, excludes)
        log(f'{bit_config.include() = }')  # type: ignore[no-untyped-call]
        log(f'{bit_config.exclude() = }')  # type: ignore[no-untyped-call]

        bit_config.SELECTIONS_MODE = selections_mode  # type: ignore[attr-defined]

        # act
        bit_snapshot.backup()  # type: ignore[no-untyped-call]

        if hasattr(bit_snapshot, '_rsync_cmd_args'):
            cmd = bit_snapshot._rsync_cmd_args
            log('rsync command arguments:')
            log('\n    '.join(arg for arg in cmd))

        last_snapshot = snapshots.lastSnapshot(bit_snapshot.config)  # type: ignore[no-untyped-call]

        try:
            backup_path = next((temp_dir / 'snapshots').glob(f'**/{last_snapshot}/backup'))
        except StopIteration:
            results_tree = filetree.normal('NONE')
        else:
            results_path = backup_path / str(files_root).strip('/')
            results_tree = filetree.tree_from_files(results_path)

        self.assertEqual(results_tree, expected_tree)

    @ddt.file_data('selection_raise_cases.yaml')
    def test_rsyncSuffix__raises(
        self,
        includes: list[str],
        excludes: list[str],
        files_tree: str,
        exception_type_name: str,
        expected_message: str,
    ) -> None:
        """Verify that running `Snapshots.backup` raises an exception.

        Args:
            includes: The list of included paths.
            excludes: The list of excluded paths.
            files_tree: The tree of files available to the backup.
            exception_type_name: e.g. "ValueError".
            expected_message: e.g. "a path is both included and excluded".
        """
        expected_exception = {
            'ValueError': ValueError,
        }[exception_type_name]

        temp_dir = get_temp_dir(self)
        bit_config = get_bit_config(temp_dir)
        bit_snapshot = snapshots.Snapshots(bit_config)  # type: ignore[no-untyped-call]

        files_root = temp_dir / "files"
        files_root.mkdir()

        includes = list(prepend_paths(files_root, includes))
        excludes = list(prepend_paths(files_root, excludes))

        files_tree = filetree.normal(files_tree)

        filetree.files_from_tree(files_root, files_tree)

        update_config(bit_config, includes, excludes)
        log(f"{bit_config.include() = }")  # type: ignore[no-untyped-call]
        log(f"{bit_config.exclude() = }")  # type: ignore[no-untyped-call]

        bit_config.SELECTIONS_MODE = 'sorted'  # type: ignore[attr-defined]

        with self.assertRaises(expected_exception) as cm:
            # act
            bit_snapshot.backup()  # type: ignore[no-untyped-call]

        self.assertRegex(cm.exception.args[0], expected_message + ":.*")


def get_temp_dir(testcase: unittest.TestCase) -> Path:
    temp_dir = tempfile.mkdtemp(prefix='backintime_testing_')
    testcase.addCleanup(shutil.rmtree, temp_dir)
    return Path(temp_dir)


def get_bit_config(temp_dir: Path) -> config.Config:
    config_path = (Path(__file__) / '../config').resolve()
    data_path = temp_dir / 'data'

    bit_config = config.Config(
        str(config_path),  # config file at backintime/common/test/config
        str(data_path),  # real default would be ~/.local/share
    )  # type: ignore[no-untyped-call]

    snapshots_path = temp_dir / 'snapshots'
    snapshots_path.mkdir()
    bit_config.set_snapshots_path(str(snapshots_path))  # type: ignore[no-untyped-call]
    tools.validate_and_prepare_snapshots_path(
        path=snapshots_path,
        host_user_profile=bit_config.hostUserProfile(),  # type: ignore[no-untyped-call]
        mode=bit_config.snapshotsMode(),  # type: ignore[no-untyped-call]
        copy_links=bit_config.copyLinks(),  # type: ignore[no-untyped-call]
        error_handler=bit_config.notifyError,
    )

    return bit_config


def prepend_paths(tmp_path: Path, paths: list[str]) -> Generator[str, None, None]:
    """Prefix any absolute paths with the temporary directory path."""
    for path in paths:
        if path == "/":
            yield f"{tmp_path}"
        elif path.startswith("/"):
            yield f"{tmp_path}{path}"
        else:
            yield f"{path}"


def update_config(
    config: config.Config,
    include_paths: list[str],
    exclude_paths: list[str],
) -> None:
    # Partly adapted from MainWindow.btnAddIncludeClicked
    includes = []

    for item in include_paths:
        if os.path.isdir(item):
            includes.append((item, 0))
        else:
            includes.append((item, 1))

    config.setInclude(includes)  # type: ignore[no-untyped-call]
    config.setExclude(exclude_paths)  # type: ignore[no-untyped-call]
