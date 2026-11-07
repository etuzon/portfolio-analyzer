"""Keep application imports during test collection away from runtime data."""
import atexit
import os
from pathlib import Path
from tempfile import TemporaryDirectory


_test_runtime = TemporaryDirectory(prefix="portfolio-pytest-")
atexit.register(_test_runtime.cleanup)
# Set these before any test module can import app.main and initialize stores.
# Individual tests can still monkeypatch their own isolated config/data paths.
os.environ["DATA_DIR"] = _test_runtime.name
os.environ["CONFIG_PATH"] = str(Path(__file__).resolve().parents[1] / "config.example.yaml")
