"""Application paths and directory bootstrapping."""
from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "hf-dataset-explorer"


def _user_data_dir() -> Path:
    """Return a per-user writable directory for app data, cross-platform."""
    env = os.environ.get("HF_EXPLORER_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / APP_NAME
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


app_dir: Path = _user_data_dir()
cache_dir: Path = app_dir / "cache"
logs_dir: Path = app_dir / "logs"

# Bootstrap directories
for _d in (app_dir, cache_dir, logs_dir):
    _d.mkdir(parents=True, exist_ok=True)

# Local storage file for favorites, history, and settings
storage_file: Path = app_dir / "storage.json"
