from collections.abc import Generator
import ddt
import os
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
from typing import Any, Union
import unittest

import pytest
from _pytest.mark.structures import ParameterSet

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


def params_for_cases(cases_file: str, selections_modes: list[str]) -> list[ParameterSet]:
    """Provide data for `test_rsyncSuffix*`.

    This parses a text file named by `cases_file`, e.g. "selection_cases", to
    provide a list of pytest `ParameterSet` objects.
    """
    cases = (Path(__file__).parent / cases_file).read_text()

    params = []

    for selections_mode in selections_modes:
        # Each case starts with a colon immediately following a newline.
        for case in (c for c in cases.split("\n:") if c.strip()):
            # The remainder of the line starting with a colon is the case_name,
            # which helps identify the test.
            case_name, rest = case.split("\n", 1)

            # Some trailing words on the case_name line that can skip the test.
            if "SKIP" in case_name:
                continue
            elif "sorted-only" in case_name:
                case_name = case_name.rsplit(None, 1)[0]
                if selections_mode != "sorted":
                    continue
            elif "original-fails" in case_name:
                case_name = case_name.rsplit(None, 1)[0]
                if selections_mode == "original":
                    continue

            # Remove trailing comments from the body of the case text.
            rest = "".join(line.split("#")[0].rstrip() + "\n" for line in rest.splitlines())

            # Make a dictionary from the body of the case text.
            specs = dict(
                re.findall(
                    r"(\w+)\n((?: .*\n)*)",
                    textwrap.dedent(rest),
                )
            )

            expected: Union[str, tuple[Any, str]] = ""

            if "expected_tree" in specs:
                expected = filetree.normal(specs["expected_tree"])
            elif "raises" in specs:
                expected_exception, expected_message = specs["raises"].split(None, 1)
                # Replace the string, e.g. "ValueError", with what it names.
                expected_exception = {**__builtins__, **globals()}[expected_exception]  # type: ignore
                expected_message = expected_message.strip()
                expected = expected_exception, expected_message
            else:
                raise ValueError(f"Missing \"expected_tree\" or \"raises\" key in {case_name}")

            params.append(
                pytest.param(
                    textwrap.dedent(specs["includes"]).splitlines(),
                    textwrap.dedent(specs["excludes"]).splitlines(),
                    filetree.normal(specs["files_tree"]),
                    expected,
                    selections_mode,
                    id=f"{selections_mode}:{case_name}",
                )
            )

    return params


@pytest.mark.parametrize(
    "includes, excludes, files_tree, expected_tree, selections_mode",
    params_for_cases("selection_cases", ["original", "sorted"]),
)
def test_rsyncSuffix(
    includes: list[str],
    excludes: list[str],
    files_tree: str,
    expected_tree: str,
    selections_mode: str,
    tmp_path: Path,
    bit_snapshot: snapshots.Snapshots,
) -> None:
    files_root = tmp_path / "files"
    files_root.mkdir()

    includes = list(prepend_paths(files_root, includes))
    excludes = list(prepend_paths(files_root, excludes))

    log(f"{files_tree =!s}")
    log(f"{expected_tree =!s}")

    filetree.files_from_tree(files_root, files_tree)

    update_config(bit_snapshot.config, includes, excludes)
    log(f"{bit_snapshot.config.include() = }")
    log(f"{bit_snapshot.config.exclude() = }")

    bit_snapshot.config.SELECTIONS_MODE = selections_mode

    # act
    bit_snapshot.backup()  # type: ignore[no-untyped-call]

    if hasattr(bit_snapshot, "_rsync_cmd_args"):
        cmd = bit_snapshot._rsync_cmd_args
        log("rsync command arguments:")
        log("\n    ".join(arg for arg in cmd))

    last_snapshot = snapshots.lastSnapshot(bit_snapshot.config)  # type: ignore[no-untyped-call]

    try:
        backup_path = next((tmp_path / "snapshots").glob(f"**/{last_snapshot}/backup"))
    except StopIteration:
        results_tree = filetree.normal("NONE")
    else:
        results_path = backup_path / str(files_root).strip("/")
        log(f"{results_path = }")
        results_tree = filetree.tree_from_files(results_path)

    assert results_tree == expected_tree


@pytest.mark.parametrize(
    "includes, excludes, files_tree, expected, selections_mode",
    params_for_cases("selection_raise_cases", ["sorted"]),
)
def test_rsyncSuffix__raises(
    includes: list[str],
    excludes: list[str],
    files_tree: str,
    expected: tuple[Any, str],
    selections_mode: str,
    tmp_path: Path,
    bit_snapshot: snapshots.Snapshots,
) -> None:
    files_root = tmp_path / "files"
    files_root.mkdir()

    includes = list(prepend_paths(files_root, includes))
    excludes = list(prepend_paths(files_root, excludes))

    expected_exception, expected_message = expected

    log("includes\n    " + "\n    ".join(p for p in includes))
    log("excludes\n    " + "\n    ".join(p for p in excludes))

    filetree.files_from_tree(files_root, files_tree)

    update_config(bit_snapshot.config, includes, excludes)
    log(f"{bit_snapshot.config.include() = }")
    log(f"{bit_snapshot.config.exclude() = }")

    bit_snapshot.config.SELECTIONS_MODE = selections_mode

    with pytest.raises(expected_exception, match=expected_message + ":.*"):
        # act
        bit_snapshot.backup()  # type: ignore[no-untyped-call]


def prepend_paths(tmp_path: Path, paths: list[str]) -> Generator[str, None, None]:
    """Prefix any absolute paths with the temporary directory path."""
    for path in paths:
        if path == "/":
            yield f"{tmp_path}"
        elif path.startswith("/"):
            yield f"{tmp_path}{path}"
        else:
            yield f"{path}"


@pytest.mark.parametrize(
    "includes, excludes, files_tree, expected_tree, selections_mode",
    params_for_cases("selection_root_cases", ["original", "sorted"]),
)
def test_rsyncSuffix__root(
    includes: list[str],
    excludes: list[str],
    files_tree: str,
    expected_tree: str,
    selections_mode: str,
    tmp_path: Path,
    bit_snapshot: snapshots.Snapshots,
) -> None:
    """Having the root directory `/` as an included directory."""

    files_root = "/"

    log(f"{files_tree =!s}")
    log(f"{expected_tree =!s}")

    update_config(bit_snapshot.config, includes, excludes)
    log(f"{bit_snapshot.config.include() = }")
    log(f"{bit_snapshot.config.exclude() = }")

    bit_snapshot.config.SELECTIONS_MODE = selections_mode

    # act
    bit_snapshot.backup()  # type: ignore[no-untyped-call]

    if hasattr(bit_snapshot, "_rsync_cmd_args"):
        cmd = bit_snapshot._rsync_cmd_args
        log("rsync command arguments:")
        log("\n    ".join(arg for arg in cmd))

    last_snapshot = snapshots.lastSnapshot(bit_snapshot.config)  # type: ignore[no-untyped-call]

    try:
        backup_path = next((tmp_path / "snapshots").glob(f"**/{last_snapshot}/backup"))
    except StopIteration:
        results_tree = filetree.normal("NONE")
    else:
        results_path = backup_path / str(files_root).strip("/")
        log(f"{results_path = }")
        results_tree = filetree.tree_from_files(results_path)

    assert results_tree == expected_tree


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
