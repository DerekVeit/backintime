from pathlib import Path
import re
import textwrap
from typing import Iterable


"""
A "tree" in this module means a multi-line text representation of files and
directories like this:

    a_tree = '''
        foo/
            bar/
                file-a
            baz/
                file-b
            file-c
    '''

This is to help make backup tests that are easy to read and write and are clear
in their expectations and results.

Key features:
- Directories are distinguished by a trailing slash
- Indentation increment must be 4 spaces
- Within a directory, names must be sorted with directories before files
- Initial indentation and leading and trailing whitespace are arbitrary
- Empty directories are allowed

Main functions:
- files_from_tree: Create a file structure from a tree representation
- tree_from_files: Generate a tree representation from an existing file structure
- normal: Normalize the indentation and whitespace of a tree string

An example of how this might be used to test a backup procedure:
    1)  empty directories A and B are created.
    2)  tree_a is defined with a string to specify some files.
    3)  files_from_tree(A, tree_a)
    4)  a backup is made from directory A to directory B.
    5)  tree_b = tree_from_files(B)
    6)  assert tree_b == normal(tree_a)
"""


def files_from_tree(parent_dir: str | Path, tree: str) -> None:
    """Create in `parent_dir` the structure described by `tree`."""
    dir_paths, file_paths = parse_tree(parent_dir, tree)

    for path in dir_paths:
        path.mkdir()

    for path in file_paths:
        path.touch()


def parse_tree(parent_dir: str | Path, tree: str) -> tuple[list[Path], list[Path]]:
    """Return the paths described by `tree` in `parent_dir`."""
    parent_path = Path(parent_dir)

    # a stack of ancestral directories at the current line
    parent_dirs: list[Path] = []
    # a stack of corresponding indentation strings
    indents: list[str] = []
    # most recent directory name in each ancestral directory
    prec_dirname: dict[Path, str] = {}
    # most recent file name in each ancestral directory
    prec_filename: dict[Path, str] = {}

    # full paths of the directories
    dir_paths = []
    # full paths of the files
    file_paths = []

    prev_filename: str = ""

    for line in tree.splitlines():
        if not line.strip():
            continue

        indent, filename = split_indent(line)

        if not re.match(r"^(?:    )*$", indent):
            raise ValueError(f"indentation must be of 4-space increments: {line = }")

        if not indents:
            # first iteration
            indents.append(indent)
            parent_dirs.append(parent_path)
        elif indent == indents[-1]:
            # the same indentation level and same parent directory
            pass
        elif indent in indents[:-1]:
            # a previous indentation level and corresponding parent directory
            index = indents.index(indent)
            indents = indents[: index + 1]
            parent_dirs = parent_dirs[: index + 1]
        elif len(indent) > len(indents[-1]):
            # should be reading the contents of a directory just seen
            if not prev_filename.endswith("/"):
                raise ValueError(f"indentation without directory: {line = }")
            indents.append(indent)
            parent_dirs.append(parent_dirs[-1] / prev_filename[:-1])
        else:
            raise ValueError(f"inconsistent tree indentation: {line = }")

        preceding_dirname_here = prec_dirname.get(parent_dirs[-1], "")
        preceding_filename_here = prec_filename.get(parent_dirs[-1], "")
        if filename.endswith("/"):
            if not preceding_dirname_here < filename:
                raise ValueError(
                    f"listed out of order after {preceding_dirname_here!r}: {line = }"
                )
            if preceding_filename_here:
                raise ValueError(f"directory cannot be listed after file(s): {line = }")

            # add the path for this directory
            dir_paths.append(parent_dirs[-1] / filename)

            prec_dirname[parent_dirs[-1]] = filename
        else:
            if not preceding_filename_here < filename:
                raise ValueError(
                    f"listed out of order after {preceding_filename_here!r}: {line = }"
                )

            # add the path for this file
            file_paths.append(parent_dirs[-1] / filename)

            prec_filename[parent_dirs[-1]] = filename

        prev_filename = filename

    return dir_paths, file_paths


def split_indent(text: str) -> tuple[str, str]:
    """Return the indentation and the remainder of the string as 2 strings."""
    mo = re.match(r"( *)(.*)", text)
    indent, remainder = mo.groups()  # type: ignore [union-attr]
    return indent, remainder


def tree_from_files(parent_dir: str | Path) -> str:
    """Return a tree describing the contents of `parent_dir`."""
    parent_path = Path(parent_dir)
    initial_depth = len(parent_path.parts)
    tree_lines = []
    for path in sort_paths(parent_path.rglob("*")):
        if path == parent_path:
            continue
        indent = "    " * (len(path.parents) - initial_depth)
        name = path.name + ("/" if path.is_dir() else "")
        tree_lines.append(indent + name)

    return "\n" + "\n".join(tree_lines) + "\n"


def normal(tree_string: str) -> str:
    """Normalize indentation depth and surrounding whitespace of the tree."""
    return f"\n{textwrap.dedent(tree_string).strip()}\n"


def sort_paths(paths: Iterable[Path]) -> list[Path]:
    """Sort a list of paths.

    Within each directory, subdirectories are listed before files.
    """
    return sorted(
        paths,
        key=lambda path: (
            [(False, part) for part in path.parts[:-1]]
            + [(not path.is_dir(), path.name)]
        ),
    )
