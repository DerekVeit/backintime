import itertools
import pathlib
import re
import textwrap

import more_itertools


def files_from_tree(parent_dir, tree):
    dir_paths, file_paths = parse_tree(parent_dir, tree)

    for path in dir_paths:
        path.mkdir()

    for path in file_paths:
        path.touch()


def parse_tree(parent_dir, tree):
    parent_dirs = []
    indents = []
    prec_dirname = {}
    prec_filename = {}

    dir_paths = []
    file_paths = []

    for line in tree.splitlines():
        if not line.strip():
            continue

        indent, filename = split_indent(line)

        if not re.match(r"^(?:    )*$", indent):
            raise ValueError(f"indentation must be of 4-space increments: {line = }")
        if not indents:
            indents.append(indent)
            parent_dirs.append(pathlib.Path(parent_dir))
        elif indent == indents[-1]:
            pass
        elif indent in indents[:-1]:
            index = indents.index(indent)
            indents = indents[: index + 1]
            parent_dirs = parent_dirs[: index + 1]
        elif len(indent) > len(indents[-1]):
            if not prev_filename.endswith("/"):
                raise ValueError(f"indentation without directory: {line = }")
            indents.append(indent)
            parent_dirs.append(parent_dirs[-1] / prev_filename[:-1])
        else:
            raise ValueError(f"inconsistent tree indentation: {line = }")

        if filename.endswith("/"):
            if not prec_dirname.get(parent_dirs[-1], "") < filename:
                raise ValueError(f"listed out of order after {prec_dirname[parent_dirs[-1]]!r}: {line = }")
            if prec_filename.get(parent_dirs[-1]):
                raise ValueError(f"directory cannot be listed after file(s): {line = }")
            dir_paths.append(parent_dirs[-1] / filename)
            prec_dirname[parent_dirs[-1]] = filename
        else:
            if not prec_filename.get(parent_dirs[-1], "") < filename:
                raise ValueError(f"listed out of order after {prec_filename[parent_dirs[-1]]!r}: {line = }")
            file_paths.append(parent_dirs[-1] / filename)
            prec_filename[parent_dirs[-1]] = filename

        prev_filename = filename

    return dir_paths, file_paths


def split_indent(text):
    mo = re.match(r"( *)(.*)", text)
    return mo.groups()


def tree_from_files(parent_dir):
    tree_lines = []

    files = [("", parent_dir)]
    while files:
        indent, path = files.pop()
        if path.is_dir():
            tree_lines.append(f"{indent}{path.name}/\n")
            subfiles, subdirs = more_itertools.partition(
                lambda p: p.is_dir(), path.iterdir()
            )
            files.extend(
                (indent + "    ", p)
                for p in itertools.chain.from_iterable(
                    (sorted(subs, reverse=True) for subs in (subfiles, subdirs))
                )
            )
        else:
            tree_lines.append(f"{indent}{path.name}\n")

    return normal("".join(tree_lines[1:]))


def normal(tree_string):
    return f"\n{textwrap.dedent(tree_string).strip()}\n"
