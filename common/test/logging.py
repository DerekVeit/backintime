import datetime
import os
import pathlib

"""
A simple log facility for use in the unit tests.  This is intentionally
independent of the stdlib-based logging used by the application.

Example:

    from test.logging import log

    def test_foo():
        log("some message")
"""

log_path = pathlib.Path("/tmp/bit-unittest.log")

current_test = ""


def log(message: str) -> None:
    """Append a message to the log file.

    This also writes a line of = before the first log message and a line
    of - and the test name before each new test case.
    """
    global current_test
    last_test, current_test = current_test, os.getenv("PYTEST_CURRENT_TEST", "--")
    timestamp = datetime.datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        if not last_test:
            f.write(f"\n{'=' * 80}\n")
        if current_test != last_test:
            f.write(f"\n{'-' * 80}\n")
            f.write(f"\n{timestamp} {current_test}\n")
        f.write(f"  {message}\n")
