import os
import pathlib
import re
import textwrap

import pytest

import snapshots

from test import filetree
from test.logging import log



def params_for_cases(cases_file):
    cases = (pathlib.Path(__file__).parent / cases_file).read_text()

    params = []
    for case in (c for c in cases.split("\n:") if c.strip()):
        case_name, rest = case.split("\n", 1)
        if "SKIP" in case_name:
            continue
        rest = "".join(line.split("#")[0].rstrip() + "\n" for line in rest.splitlines())
        specs = dict(
            re.findall(
                r"(\w+)\n((?: .*\n)*)",
                textwrap.dedent(rest),
            )
        )
        params.append(
            pytest.param(
                textwrap.dedent(specs["includes"]).splitlines(),
                textwrap.dedent(specs["excludes"]).splitlines(),
                filetree.normal(specs["files_tree"]),
                filetree.normal(specs["expected_tree"]),
                id=case_name,
            )
        )
    return params


def params_for_raise_cases(cases_file):
    cases = (pathlib.Path(__file__).parent / cases_file).read_text()

    params = []
    for case in (c for c in cases.split("\n:") if c.strip()):
        case_name, rest = case.split("\n", 1)
        if "SKIP" in case_name:
            continue
        rest = "".join(line.split("#")[0].rstrip() + "\n" for line in rest.splitlines())
        specs = dict(
            re.findall(
                r"(\w+)\n((?: .*\n)*)",
                textwrap.dedent(rest),
            )
        )
        expected_exception, expected_message = specs["raises"].split(None, 1)
        expected_exception = {**__builtins__, **globals()}[expected_exception]
        expected_message = expected_message.strip()
        params.append(
            pytest.param(
                textwrap.dedent(specs["includes"]).splitlines(),
                textwrap.dedent(specs["excludes"]).splitlines(),
                filetree.normal(specs["files_tree"]),
                expected_exception,
                expected_message,
                id=case_name,
            )
        )
    return params


@pytest.mark.parametrize(
    "includes, excludes, files_tree, expected_tree",
    params_for_cases("selection_cases"),
)
def test_rsyncSuffix(
    includes, excludes, files_tree, expected_tree, tmp_path, bit_snapshot
):
    includes, excludes = prepend_paths(tmp_path, includes, excludes)

    log(f"{files_tree =!s}")
    log(f"{expected_tree =!s}")

    filetree.files_from_tree(tmp_path, files_tree)

    add_includes(bit_snapshot.config, includes)
    log(f"{bit_snapshot.config.include() = }")

    bit_snapshot.config.setExclude(bit_snapshot.config.exclude() + excludes)
    log(f"{bit_snapshot.config.exclude() = }")

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
        results_path = backup_path / str(tmp_path).strip("/")
        log(f"{results_path = }")
        results_tree = filetree.tree_from_files(results_path)

    assert results_tree == expected_tree


@pytest.mark.parametrize(
    "includes, excludes, files_tree, expected_exception, expected_message",
    params_for_raise_cases("selection_raise_cases"),
)
def test_rsyncSuffix__raises(
    includes, excludes, files_tree, expected_exception, expected_message, tmp_path, bit_snapshot
):
    includes, excludes = prepend_paths(tmp_path, includes, excludes)

    log("\n  ".join(p for p in includes))
    log("\n  ".join(p for p in excludes))

    filetree.files_from_tree(tmp_path, files_tree)

    add_includes(bit_snapshot.config, includes)
    log(f"{bit_snapshot.config.include() = }")

    bit_snapshot.config.setExclude(bit_snapshot.config.exclude() + excludes)
    log(f"{bit_snapshot.config.exclude() = }")

    with pytest.raises(ValueError, match=expected_message + ":.*"):
        bit_snapshot.backup()


def prepend_paths(tmp_path, includes, excludes):
    includes = [f"{tmp_path}{p}" if p.startswith("/") else p for p in includes]
    excludes = [f"{tmp_path}{p}" if p.startswith("/") else p for p in excludes]
    return includes, excludes


def add_includes(config, paths):
    # Adapted from MainWindow.btnAddIncludeClicked
    #include = config.include()
    include = []

    for item in paths:
        if os.path.isdir(item):
            include.append((item, 0))
        else:
            include.append((item, 1))

    config.setInclude(include)
