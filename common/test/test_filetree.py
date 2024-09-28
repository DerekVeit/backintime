import pytest

from test import filetree


def test_files_from_tree(tmp_path):
    tree = """
        var/
            log/
                another
                syslog
            some_file
    """
    filetree.files_from_tree(tmp_path, tree)
    assert (tmp_path / "var").is_dir()
    assert (tmp_path / "var/log").is_dir()
    assert (tmp_path / "var/log/another").is_file()
    assert (tmp_path / "var/log/syslog").is_file()
    assert (tmp_path / "var/some_file").is_file()


def test_files_from_tree__indent_not4sp(tmp_path):
    tree = """
       var
    """
    with pytest.raises(
        ValueError,
        match="indentation must be of 4-space increments: line = '       var'",
    ):
        filetree.files_from_tree(tmp_path, tree)


def test_files_from_tree__indent_not_in_dir(tmp_path):
    tree = """
        var
            some_file
    """
    with pytest.raises(
        ValueError,
        match="indentation without directory: line = '            some_file'",
    ):
        filetree.files_from_tree(tmp_path, tree)


def test_files_from_tree__indent_inconsistent(tmp_path):
    tree = """
        var
    some_file
    """
    with pytest.raises(
        ValueError,
        match="inconsistent tree indentation: line = '    some_file'",
    ):
        filetree.files_from_tree(tmp_path, tree)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("    some text", ("    ", "some text")),
        ("some text", ("", "some text")),
        ("    ", ("    ", "")),
        ("", ("", "")),
    ],
)
def test_split_indent(text, expected):
    assert filetree.split_indent(text) == expected


# fmt: off
@pytest.mark.parametrize(
    "tree",
    [
        pytest.param("""
        var/
            lib/
                libsubdir/
                    sub_file
                some_lib
            log/
                box/
                    contents
                another
                syslog
            some_file
            temp_file
        """, id='1'),
        pytest.param("""
        """, id='2'),
        pytest.param("""
        .hidden_file1
        file2
        """, id='3'),
        pytest.param("""
        dir1/
        """, id='4'),
    ]
)
# fmt: on
def test_tree_from_files(tmp_path, tree):
    filetree.files_from_tree(tmp_path, tree)
    result = filetree.tree_from_files(tmp_path)
    assert result == filetree.normal(tree)


def test_tree_from_files__raise_dir_late(tmp_path):
    tree = """
        var/
            foo
            lib/
    """
    with pytest.raises(ValueError, match="directory cannot be listed after file.*"):
        filetree.files_from_tree(tmp_path, tree)


def test_tree_from_files__raise_dir_order(tmp_path):
    tree = """
        var/
            log/
            lib/
    """
    with pytest.raises(ValueError, match="listed out of order .*"):
        filetree.files_from_tree(tmp_path, tree)


def test_tree_from_files__raise_file_order(tmp_path):
    tree = """
        var/
            foo
            bar
    """
    with pytest.raises(ValueError, match="listed out of order .*"):
        filetree.files_from_tree(tmp_path, tree)


# fmt: off
@pytest.mark.parametrize(
    "input_tree",
    [
        pytest.param("""
a/
    b/
        c/
            c1
    a1
""", id='1'),
        pytest.param("""
    a/
        b/
            c/
                c1
        a1
        """, id='2'),
        pytest.param("""    a/
        b/
            c/
                c1
        a1""", id='3'),
    ]
)
def test_normal(input_tree):
    assert filetree.normal(input_tree) == """
a/
    b/
        c/
            c1
    a1
"""
# fmt: on
