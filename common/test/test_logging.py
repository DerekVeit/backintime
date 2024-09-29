from pathlib import Path
import re

import pytest

from test import logging
from test.logging import log


def test_log__first_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the initial log entry for a test."""
    monkeypatch.setattr(logging, "log_path", tmp_path / "bit-unittest.log")
    monkeypatch.setattr(logging, "current_test", "")

    log("some message")
    log("another message")

    file_contents = logging.log_path.read_text()
    assert re.search(
        r"""\n[0-9-]+ [0-9:]+ .*/test_logging\.py::test_log.*
  some message
  another message
""",
        file_contents,
    )


def test_log__subsequent_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a subsequent log entry for a test."""
    monkeypatch.setattr(logging, "log_path", tmp_path / "bit-unittest.log")
    monkeypatch.setattr(logging, "current_test", "test_other.py::test_other (call)")

    log("some message")
    log("another message")

    file_contents = logging.log_path.read_text()
    assert re.search(
        r"""[0-9-]+ [0-9:]+ .*/test_logging\.py::test_log.*
  some message
  another message
""",
        file_contents,
    )
