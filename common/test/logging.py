import datetime
import os
import pathlib


log_path = pathlib.Path("/tmp/bit-unittest.log")

current_test = ""


def log(message):
    global current_test
    last_test, current_test = current_test, os.getenv("PYTEST_CURRENT_TEST", "--")
    timestamp = datetime.datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        if not last_test:
            f.write("\n")
        if current_test != last_test:
            f.write(f"{timestamp} {current_test}\n")
        f.write(f"  {message}\n")
