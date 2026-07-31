"""Shared pytest configuration."""

import sys
from pathlib import Path

# Since the application runs with app/ as its source root (uvicorn is started
# with `--app-dir app`), the app/ directory must be added to the Python search
# path.
# By resolving the path of app/ from this file's location, the tests
# import the application's modules the same way regardless of the runner's
# working directory.
APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
