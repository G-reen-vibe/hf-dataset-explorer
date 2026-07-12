"""
HuggingFace Hub API client for datasets.

Endpoints used (all under https://huggingface.co/api):
  GET /datasets                       - list datasets with filters
  GET /datasets/{repo_id}             - dataset metadata + cardData + siblings
  GET /datasets/{repo_id}/parquet     - parquet file URLs per config/split
  GET /datasets/{repo_id}/parquet/{config}/{split}/{n}.parquet
                                      - actual parquet bytes (returns rows)

This module is intentionally synchronous (Flet can call it from a thread via
page.run_task / page.run_thread) and uses an in-memory TTL cache to avoid
hammering the API when the user clicks around.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

HF_BASE = "https://huggingface.co/api"
HF_DATASETS_SERVER = "https://datasets-server.huggingface.co"
HF_PARQUET_ROW_LIMIT = 100  # how many rows to fetch for the dataset viewer preview
DEFAULT_TIMEOUT = 20  # seconds
CACHE_TTL = 300  # 5 minutes for metadata caches


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

class _TTLCache:
    """Tiny thread-safe TTL cache."""

    def __init__(self, ttl: int = CACHE_TTL):
        self._ttl = ttl
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            ts, val = item
            if time.time() - ts > self._ttl:
                self._store.pop(key, None)
                return None
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache = _TTLCache()


def clear_cache() -> None:
    _cache.clear()


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class HFError(Exception):
    """Raised when the HuggingFace API returns an error."""

    def __init__(self, message: str, status: int = 0, url: str = ""):
        super().__init__(message)
        self.status = status
        self.url = url


class HFClient:
    """Lightweight HuggingFace datasets API client."""

    def __init__(self, token: str = "", timeout: int = DEFAULT_TIMEOUT):
        self.token = (token or "").strip()
        self.timeout = timeout
        self._session = requests.Session()
        if self.token:
            self._session.headers["Authorization"] = f"Bearer {self.token}"
        self._session.headers["User-Agent"] = "hf-dataset-explorer/1.0"

    # ----- low-level -------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, *,
             use_cache: bool = True, cache_key: Optional[str] = None) -> Any:
        url = f"{HF_BASE}{path}" if path.startswith("/") else path
        key = cache_key or self._cache_key(url, params)
        if use_cache:
            cached = _cache.get(key)
            if cached is not None:
                return cached
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as ex:
            raise HFError(f"Network error: {ex}", url=url) from ex
        if resp.status_code == 404:
            raise HFError(f"Not found: {url}", status=404, url=url)
        if resp.status_code == 401:
            raise HFError("Authentication required. Check your API token.",
                          status=401, url=url)
        if resp.status_code == 429:
            raise HFError("Rate limit exceeded. Please wait a moment and try again.",
                          status=429, url=url)
        if not resp.ok:
            raise HFError(f"API error {resp.status_code}: {resp.text[:200]}",
                          status=resp.status_code, url=url)
        try:
            data = resp.json()
        except ValueError as ex:
            raise HFError(f"Invalid JSON response: {ex}", url=url) from ex
        if use_cache:
            _cache.set(key, data)
        return data

    @staticmethod
    def _cache_key(url: str, params: Optional[Dict[str, Any]]) -> str:
        if not params:
            return url
        return url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    # ----- high-level ------------------------------------------------------

    def list_datasets(
        self,
        *,
        search: str = "",
        author: str = "",
        tags: Optional[List[str]] = None,
        sort: str = "downloads",  # downloads | likes | createdAt | lastModified
        direction: int = -1,
        limit: int = 30,
        offset: int = 0,
        full: bool = True,
    ) -> List[Dict[str, Any]]:
        """List datasets with filters. Returns a list of dataset summary dicts.

        Note: the HuggingFace API supports these sort values:
        - 'downloads' — most downloaded
        - 'likes' — most liked
        - 'createdAt' — most recently created
        - 'lastModified' — most recently modified

        The legacy 'trending'/'created'/'modified' values are normalized to
        their canonical API names below.
        """
        # Normalize legacy sort values to the API's canonical names
        sort_aliases = {
            "trending": "downloads",  # trending score isn't directly sortable; use downloads as proxy
            "created": "createdAt",
            "modified": "lastModified",
        }
        sort = sort_aliases.get(sort, sort)

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort": sort,
            "direction": direction,
            "full": str(full).lower(),
        }
        if search:
            params["search"] = search
        if author:
            params["author"] = author
        if tags:
            params["filter"] = ",".join(tags)
        data = self._get("/datasets", params=params, use_cache=True)
        if not isinstance(data, list):
            return []
        return data

    def get_dataset(self, repo_id: str) -> Dict[str, Any]:
        """Get full dataset metadata."""
        # Don't cache forever — full metadata can change.
        return self._get(f"/datasets/{repo_id}", use_cache=True,
                         cache_key=f"/datasets/{repo_id}:full")

    def get_parquet_listing(self, repo_id: str) -> Dict[str, Any]:
        """Get the parquet file listing per config/split."""
        return self._get(f"/datasets/{repo_id}/parquet", use_cache=True,
                         cache_key=f"/datasets/{repo_id}:parquet")

    def get_rows(self, repo_id: str, config: str, split: str,
                 offset: int = 0, length: int = 100) -> Dict[str, Any]:
        """Fetch rows from a dataset via the HuggingFace Datasets Server.

        Endpoint: https://datasets-server.huggingface.co/rows
        """
        params = {
            "dataset": repo_id,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        }
        url = f"{HF_DATASETS_SERVER}/rows"
        # Rows endpoint is not cached — it can return huge payloads.
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as ex:
            raise HFError(f"Network error fetching rows: {ex}", url=url) from ex
        if resp.status_code == 404:
            raise HFError(
                "Rows API not available for this dataset. "
                "It may use a non-parquet format, be gated, or require special handling.",
                status=404, url=url,
            )
        if not resp.ok:
            raise HFError(f"Rows API error {resp.status_code}: {resp.text[:200]}",
                          status=resp.status_code, url=url)
        return resp.json()

    # ----- aggregate helpers ----------------------------------------------

    def get_trending(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get trending datasets (approximated via downloads + high trendingScore).

        The HF API doesn't expose 'trending' as a direct sort option, so we
        fetch by downloads (which correlates strongly with trending).
        """
        return self.list_datasets(sort="downloads", direction=-1, limit=limit)

    def get_most_downloaded(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.list_datasets(sort="downloads", direction=-1, limit=limit)

    def get_most_liked(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.list_datasets(sort="likes", direction=-1, limit=limit)

    def get_recent(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.list_datasets(sort="createdAt", direction=-1, limit=limit)

    def get_recently_updated(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self.list_datasets(sort="lastModified", direction=-1, limit=limit)


# --------------------------------------------------------------------------- #
# Module-level singleton for convenience
# --------------------------------------------------------------------------- #

_client_lock = threading.Lock()
_client: Optional[HFClient] = None


def get_client(token: str = "") -> HFClient:
    """Return a process-wide HFClient. Recreates it if the token changes."""
    global _client
    with _client_lock:
        if _client is None or (_client.token or "") != (token or "").strip():
            _client = HFClient(token=token)
        return _client


# --------------------------------------------------------------------------- #
# Tag taxonomy (used to power the filter UI)
# --------------------------------------------------------------------------- #

TASK_CATEGORIES = [
    "task_categories:text-generation",
    "task_categories:text-classification",
    "task_categories:token-classification",
    "task_categories:question-answering",
    "task_categories:translation",
    "task_categories:summarization",
    "task_categories:fill-mask",
    "task_categories:image-classification",
    "task_categories:image-segmentation",
    "task_categories:object-detection",
    "task_categories:speech-recognition",
    "task_categories:text-to-speech",
    "task_categories:conversational",
    "task_categories:table-question-answering",
    "task_categories:reinforcement-learning",
    "task_categories:robotics",
    "task_categories:other",
]

MODALITIES = [
    "modality:text",
    "modality:image",
    "modality:audio",
    "modality:video",
    "modality:tabular",
    "modality:3d",
    "modality:timeseries",
]

SIZE_CATEGORIES = [
    "size_categories:n<1K",
    "size_categories:1K<n<10K",
    "size_categories:10K<n<100K",
    "size_categories:100K<n<1M",
    "size_categories:1M<n<10M",
    "size_categories:10M<n<100M",
    "size_categories:100M<n<1B",
    "size_categories:1B<n<10B",
    "size_categories:10B<n<100B",
    "size_categories:100B<n<1T",
    "size_categories:n>1T",
]

LICENSES = [
    "license:mit",
    "license:apache-2.0",
    "license:cc-by-4.0",
    "license:cc-by-sa-4.0",
    "license:cc-by-nc-4.0",
    "license:cc0-1.0",
    "license:bsd-3-clause",
    "license:gpl-3.0",
    "license:lgpl-3.0",
    "license:mpl-2.0",
    "license:openrail",
    "license:other",
]

FORMATS = [
    "format:parquet",
    "format:json",
    "format:csv",
    "format:arrow",
    "format:imagefolder",
    "format:audiofolder",
    "format:webdataset",
    "format:mlcroissant",
]


def categorize_tag(tag: str) -> str:
    """Return the category name for a HF tag, or '' if uncategorized."""
    if tag.startswith("task_categories:"):
        return "task"
    if tag.startswith("modality:"):
        return "modality"
    if tag.startswith("size_categories:"):
        return "size"
    if tag.startswith("language:"):
        return "language"
    if tag.startswith("license:"):
        return "license"
    if tag.startswith("format:"):
        return "format"
    if tag.startswith("library:"):
        return "library"
    if tag.startswith("region:"):
        return "region"
    if tag.startswith("arxiv:"):
        return "arxiv"
    return ""


def parse_tags(tags: List[str]) -> Dict[str, List[str]]:
    """Group a list of HF tags into a dict by category."""
    out: Dict[str, List[str]] = {}
    for t in tags or []:
        cat = categorize_tag(t)
        if not cat:
            continue
        out.setdefault(cat, []).append(t)
    return out
