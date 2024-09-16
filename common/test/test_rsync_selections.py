import os
import pathlib
import re
import textwrap

import pytest

import snapshots

from test import filetree
from test.logging import log


def params_for_cases(cases_file, selections_modes):
    """Provide data for `test_rsyncSuffix*`.

    This parses a text file named by `cases_file`, e.g. "selection_cases", to
    provide a list of pytest `ParameterSet` objects.
    """
    cases = (pathlib.Path(__file__).parent / cases_file).read_text()

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

            if "expected_tree" in specs:
                expected = filetree.normal(specs["expected_tree"])
            elif "raises" in specs:
                expected_exception, expected_message = specs["raises"].split(None, 1)
                # Replace the string, e.g. "ValueError", with what it names.
                expected_exception = {**__builtins__, **globals()}[expected_exception]
                expected_message = expected_message.strip()
                expected = expected_exception, expected_message

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
    includes,
    excludes,
    files_tree,
    expected_tree,
    selections_mode,
    tmp_path,
    bit_snapshot,
):
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

    bit_snapshot.backup()

    if hasattr(bit_snapshot, "_rsync_cmd_args"):
        cmd = bit_snapshot._rsync_cmd_args
        log("rsync command arguments:")
        log("\n    ".join(arg for arg in cmd))

    last_snapshot = snapshots.lastSnapshot(bit_snapshot.config)

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
    includes,
    excludes,
    files_tree,
    expected,
    selections_mode,
    tmp_path,
    bit_snapshot,
):
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
        bit_snapshot.backup()


def prepend_paths(tmp_path, paths):
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
    includes,
    excludes,
    files_tree,
    expected_tree,
    selections_mode,
    tmp_path,
    bit_snapshot,
):
    """Having the root directory `/` as an included directory."""


    files_root = "/"

    log(f"{files_tree =!s}")
    log(f"{expected_tree =!s}")

    update_config(bit_snapshot.config, includes, excludes)
    log(f"{bit_snapshot.config.include() = }")
    log(f"{bit_snapshot.config.exclude() = }")

    bit_snapshot.config.SELECTIONS_MODE = selections_mode

    bit_snapshot.backup()

    if hasattr(bit_snapshot, "_rsync_cmd_args"):
        cmd = bit_snapshot._rsync_cmd_args
        log("rsync command arguments:")
        log("\n    ".join(arg for arg in cmd))

    last_snapshot = snapshots.lastSnapshot(bit_snapshot.config)

    try:
        backup_path = next((tmp_path / "snapshots").glob(f"**/{last_snapshot}/backup"))
    except StopIteration:
        results_tree = filetree.normal("NONE")
    else:
        results_path = backup_path / str(files_root).strip("/")
        log(f"{results_path = }")
        results_tree = filetree.tree_from_files(results_path)

    assert results_tree == expected_tree


def update_config(config, include_paths, exclude_paths):
    # Partly adapted from MainWindow.btnAddIncludeClicked
    includes = []

    for item in include_paths:
        if os.path.isdir(item):
            includes.append((item, 0))
        else:
            includes.append((item, 1))

    config.setInclude(includes)
    config.setExclude(exclude_paths)
