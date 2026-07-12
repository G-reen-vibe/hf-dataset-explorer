# HF Dataset Explorer

A production-grade desktop application for browsing, analyzing, and comparing datasets on the [HuggingFace Hub](https://huggingface.co/datasets). Built with [Flet](https://flet.dev) and Python.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flet](https://img.shields.io/badge/Flet-0.85+-orange)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

### 🔍 Explore
- **Full-text search** across all public datasets on the Hub
- **Filter by** task category, modality, size, license, and format
- **Sort by** downloads, likes, recency, or last-modified
- **Quick filter chips** for common categories (trending, text generation, image classification, etc.)
- **Pagination** with "Load more" support
- **Inline favorite toggle** on every result card

### 📊 Dataset Detail
- **Full metadata view** with all stats (downloads, likes, trending score, examples, sizes)
- **Schema browser** showing features and their data types
- **Splits table** with example counts and byte sizes per split
- **Configuration list** with chips
- **Dataset viewer** that fetches actual rows via the HuggingFace Datasets Server
  - Config / split / rows-per-page selectors
  - Pagination (Previous / Next)
  - Smart cell formatting for strings, numbers, lists, and dicts
- **File listing** with type-aware icons and sizes
- **Description viewer** with lightweight Markdown stripping and "Show more" expansion
- **Tag overview** grouped by category (task, modality, size, language, license, format)
- **Open on HuggingFace** button for jumping to the web UI
- **Favorite / unfavorite** from the detail header

### 📈 Analytics
- **KPI tiles** showing total downloads, likes, average trending, and unique authors across a configurable sample (50/100/200/500 datasets)
- **Top 10 by downloads** — horizontal bar chart
- **Top 10 by likes** — horizontal bar chart
- **Top 10 trending** — horizontal bar chart
- **Tag distribution** — category breakdown with counts and percentages
- **Top authors** — by dataset count and aggregate downloads

### ⚖️ Compare
- Side-by-side comparison of up to **4 datasets**
- **Add datasets by ID** or pre-load from favorites
- **Best-value highlighting** in each row (best downloads, best likes, etc.)
- Compares: downloads, likes, trending, examples, sizes, dates, license, tasks, modalities, size category

### ❤️ Favorites & 🕐 History
- **Favorites**: locally-persisted saved datasets
- **History**: recently-viewed datasets with timestamps (most-recent-first, deduplicated)
- **Configurable history limit** (default 50, adjustable in Settings)
- Both views support opening, favoriting, and clearing

### ⚙️ Settings
- **API token** configuration (optional — most public datasets work without one)
- **Theme switcher**: Dark / Light / System
- **History limit** adjustment
- **Cache clearing** for API responses
- **Reset all data** (clears favorites + history)
- Links to HuggingFace token page and Flet docs

## Installation

### Prerequisites
- Python 3.10 or newer
- `pip` package manager

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the app
```bash
python main.py
```

The first run will create a per-user data directory:
- **Linux**: `~/.local/share/hf-dataset-explorer/`
- **macOS**: `~/Library/Application Support/hf-dataset-explorer/`
- **Windows**: `%APPDATA%\hf-dataset-explorer\`

This directory holds `storage.json` (favorites, history, settings) and `logs/explorer.log`.

## Architecture

The app follows a layered architecture inspired by the [medical-record-management-assistant](https://github.com/Lilian-Moon11/medical-record-management-assistant) reference project:

```
hf-dataset-explorer/
├── main.py                    # Entry point & composition root
├── requirements.txt
├── conftest.py                # pytest configuration (E2E marker)
│
├── core/                      # Core infrastructure
│   ├── paths.py               # Cross-platform path bootstrap
│   ├── app_state.py           # Per-page session state (page.hf namespace)
│   └── storage.py             # JSON-backed favorites, history, settings
│
├── api/                       # External API client
│   └── hf_client.py           # HuggingFace API client with TTL cache
│
├── ui/                        # UI shell
│   ├── theme.py               # Light/dark Flet theme definitions
│   ├── navigation.py          # Top nav bar + content area shell
│   └── routing.py             # View factory + dataset detail navigation
│
├── views/                     # One module per top-level view
│   ├── explore.py             # Browse + search + filter
│   ├── dataset_detail.py      # Full dataset metadata + viewer
│   ├── analytics.py           # Aggregate charts and stats
│   ├── compare.py             # Side-by-side comparison
│   ├── favorites.py           # Saved datasets
│   ├── history.py             # Recently viewed
│   └── settings.py            # API token, theme, cache
│
├── utils/                     # Shared utilities
│   ├── formatters.py          # Number / byte / date / tag / markdown formatters
│   └── ui_helpers.py          # Cards, chips, stat tiles, snackbars
│
├── tests/                     # Unit + integration + E2E tests
│   ├── test_hf_client.py      # API client (mocked)
│   ├── test_storage.py        # Local storage
│   ├── test_formatters.py     # Formatters
│   ├── test_integration.py    # Module wiring
│   ├── test_app_smoke.py      # App construction smoke test
│   └── test_e2e_api.py        # Live API tests (skip by default)
│
└── scripts/
    └── runtime_test.py        # Launches the app in web mode for verification
```

### Key design decisions

1. **Synchronous API client** — All network calls happen in background threads via `page.run_thread(...)`, keeping the UI responsive. The `HFClient` class is intentionally synchronous and uses an in-memory TTL cache to avoid hammering the API.

2. **Per-page state namespace** — `page.hf` is a `types.SimpleNamespace` that holds the per-session state (search query, current view, back stack, etc.). This keeps state out of global variables while remaining easy to access.

3. **Lazy view construction** — Views are built on-demand by `make_get_view_for_index` each time the user switches tabs. This avoids holding stale control references and lets the view reflect the latest state.

4. **Local JSON storage** — Favorites, history, and settings are persisted in a single `storage.json` file with thread-safe read/write helpers. No external database is needed.

5. **Theme separation** — Light and dark themes are defined declaratively in `ui/theme.py`. The active theme is read from `storage.get_setting("theme_mode")` and applied via `apply_theme(page)`.

6. **Tag taxonomy** — HuggingFace tags follow a `category:value` convention (e.g. `task_categories:text-generation`). The `categorize_tag` and `parse_tags` helpers group tags by category, powering both the filter UI and the analytics tag distribution.

## API Endpoints Used

All endpoints are public and don't require authentication for public datasets:

| Endpoint | Purpose |
|----------|---------|
| `GET https://huggingface.co/api/datasets` | List datasets with filters (search, author, tags, sort) |
| `GET https://huggingface.co/api/datasets/{repo_id}` | Full dataset metadata (cardData, siblings, stats) |
| `GET https://huggingface.co/api/datasets/{repo_id}/parquet` | Parquet file listing per config/split |
| `GET https://datasets-server.huggingface.co/rows` | Row preview via the Datasets Server |

Note: The HuggingFace API supports `downloads`, `likes`, `createdAt`, and `lastModified` as sort values. The legacy `trending`, `created`, and `modified` values are normalized to their canonical names by `HFClient.list_datasets`.

## Testing

The project includes 101 tests across 5 test files:

```bash
# Run unit tests only (no network calls)
python -m pytest tests/

# Run all tests including live API E2E tests
python -m pytest tests/ --run-e2e
```

| Test file | What it covers |
|-----------|----------------|
| `test_hf_client.py` | HFClient construction, error handling, param building, sort normalization, cache key |
| `test_storage.py` | Favorites add/remove/toggle/persist, history ordering/dedup/limit, settings |
| `test_formatters.py` | Number, byte, date, tag, markdown, dataset stats formatters |
| `test_integration.py` | Module imports, view factory, navigation destinations |
| `test_app_smoke.py` | main.py compilation, app construction with mock Page |
| `test_e2e_api.py` | Live API calls: list, search, get, parquet, rows, trending, most-downloaded |

## Keyboard Shortcuts

- `Ctrl+1` to `Ctrl+6` — Switch between Explore / Analytics / Compare / Favorites / History / Settings
- `Enter` in the search field — Trigger search
- `Escape` in dialogs — Close the active dialog

## License

MIT
