"""Local JSON-backed storage for favorites, view history, and settings."""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional

from core import paths


_LOCK = threading.Lock()


def _load() -> Dict[str, Any]:
    if not paths.storage_file.exists():
        return _default()
    try:
        with paths.storage_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default()
        # Merge in any new default keys
        merged = _default()
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return _default()


def _save(data: Dict[str, Any]) -> None:
    paths.storage_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.storage_file.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(paths.storage_file)


def _default() -> Dict[str, Any]:
    return {
        "favorites": [],          # list of dataset summary dicts
        "history": [],            # list of dataset summary dicts (most recent first)
        "settings": {
            "api_token": "",
            "theme_mode": "dark",
            "history_limit": 50,
        },
    }


# ---------- Favorites ----------

def list_favorites() -> List[Dict[str, Any]]:
    with _LOCK:
        return list(_load()["favorites"])


def is_favorite(dataset_id: str) -> bool:
    with _LOCK:
        data = _load()
        return any(d.get("id") == dataset_id for d in data["favorites"])


def add_favorite(dataset: Dict[str, Any]) -> bool:
    """Add a dataset to favorites. Returns True if added, False if already present."""
    with _LOCK:
        data = _load()
        if any(d.get("id") == dataset.get("id") for d in data["favorites"]):
            return False
        data["favorites"].append(_slim(dataset))
        _save(data)
        return True


def remove_favorite(dataset_id: str) -> bool:
    with _LOCK:
        data = _load()
        before = len(data["favorites"])
        data["favorites"] = [d for d in data["favorites"] if d.get("id") != dataset_id]
        if len(data["favorites"]) != before:
            _save(data)
            return True
        return False


def toggle_favorite(dataset: Dict[str, Any]) -> bool:
    """Toggle favorite state. Returns new state (True = now favorite)."""
    if is_favorite(dataset.get("id", "")):
        remove_favorite(dataset.get("id", ""))
        return False
    add_favorite(dataset)
    return True


# ---------- History ----------

def list_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    with _LOCK:
        data = _load()
        items = list(data["history"])
    if limit is not None:
        items = items[:limit]
    return items


def add_history(dataset: Dict[str, Any]) -> None:
    with _LOCK:
        data = _load()
        dataset_id = dataset.get("id")
        # Remove existing entry for this dataset
        data["history"] = [d for d in data["history"] if d.get("id") != dataset_id]
        # Insert slim copy at the front with timestamp
        slim = _slim(dataset)
        slim["viewed_at"] = int(time.time())
        data["history"].insert(0, slim)
        # Trim to limit
        limit = int(data["settings"].get("history_limit", 50))
        data["history"] = data["history"][:limit]
        _save(data)


def clear_history() -> None:
    with _LOCK:
        data = _load()
        data["history"] = []
        _save(data)


# ---------- Settings ----------

def get_settings() -> Dict[str, Any]:
    with _LOCK:
        return dict(_load()["settings"])


def get_setting(key: str, default: Any = None) -> Any:
    with _LOCK:
        return _load()["settings"].get(key, default)


def set_setting(key: str, value: Any) -> None:
    with _LOCK:
        data = _load()
        data["settings"][key] = value
        _save(data)


# ---------- Helpers ----------

def _slim(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a full dataset dict to the fields we actually want to persist."""
    return {
        "id": dataset.get("id"),
        "author": dataset.get("author"),
        "lastModified": dataset.get("lastModified"),
        "likes": dataset.get("likes", 0),
        "downloads": dataset.get("downloads", 0),
        "trendingScore": dataset.get("trendingScore", 0),
        "tags": dataset.get("tags", [])[:20],
        "description": (dataset.get("description") or "")[:500],
    }
