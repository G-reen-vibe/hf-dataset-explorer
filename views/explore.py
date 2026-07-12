"""Explore view: browse, search, and filter HuggingFace datasets."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import flet as ft

from api.hf_client import (
    FORMATS,
    LICENSES,
    MODALITIES,
    SIZE_CATEGORIES,
    TASK_CATEGORIES,
    HFError,
    get_client,
)
from core import app_state, storage
from ui.theme import effective_theme_mode
from utils.ui_helpers import (
    ACCENT,
    INFO,
    PRIMARY,
    SUCCESS,
    WARNING,
    dataset_card,
    empty_view,
    error_view,
    loading_view,
    muted_text_color,
    page_container,
    secondary_button,
    section_header,
    show_error,
    show_success,
    surface_bg,
    text_color,
)

logger = logging.getLogger(__name__)


_SORT_OPTIONS = [
    ("downloads", "Most Downloaded"),
    ("likes", "Most Liked"),
    ("createdAt", "Recently Created"),
    ("lastModified", "Recently Updated"),
]


def get_explore_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)

    # Restore state
    search_query = app_state.get(page, "search_query", "")
    search_author = app_state.get(page, "search_author", "")
    search_tags = app_state.get(page, "search_tags", []) or []
    selected_sort = app_state.get(page, "selected_sort", "downloads")

    # State container for this view instance
    state = {
        "query": search_query,
        "author": search_author,
        "tags": list(search_tags),
        "sort": selected_sort,
        "results": [],
        "loading": False,
        "error": None,
        "limit": 30,
        "offset": 0,
        "total_loaded": 0,
    }

    # ----- UI Controls ----------------------------------------------------
    search_field = ft.TextField(
        value=state["query"],
        hint_text="Search datasets by name or description…",
        hint_style=ft.TextStyle(color=muted_text_color(theme_mode)),
        prefix_icon=ft.Icons.SEARCH,
        border_color=ft.Colors.with_opacity(0.2, text_color(theme_mode)),
        focused_border_color=PRIMARY,
        border_radius=8,
        text_size=13,
        dense=True,
        expand=True,
        on_submit=lambda e: _do_search(page, state, e.control.value, results_col,
                                       stats_row, theme_mode),
    )

    author_field = ft.TextField(
        value=state["author"],
        hint_text="Author / organization",
        hint_style=ft.TextStyle(color=muted_text_color(theme_mode)),
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        border_color=ft.Colors.with_opacity(0.2, text_color(theme_mode)),
        focused_border_color=PRIMARY,
        border_radius=8,
        text_size=13,
        dense=True,
        width=200,
        on_submit=lambda e: _do_search(page, state, search_field.value,
                                       results_col, stats_row, theme_mode,
                                       author=e.control.value),
    )

    sort_dropdown = ft.Dropdown(
        value=state["sort"],
        options=[ft.dropdown.Option(key=k, text=v) for k, v in _SORT_OPTIONS],
        dense=True,
        border_color=ft.Colors.with_opacity(0.2, text_color(theme_mode)),
        border_radius=8,
        text_size=13,
        width=200,
        on_select=lambda e: _do_search(page, state, search_field.value,
                                       results_col, stats_row, theme_mode,
                                       sort=e.control.value, author=author_field.value),
    )

    # Filter chips container
    filter_chips_row = ft.Row(spacing=6, wrap=True, scroll=ft.ScrollMode.AUTO)

    # ----- Stats row (shows count + clear button) -------------------------
    stats_text = ft.Text("Ready to search", size=12,
                         color=muted_text_color(theme_mode))
    clear_btn = ft.TextButton(
        "Clear filters",
        icon=ft.Icons.CLEAR_ALL,
        on_click=lambda e: _clear_filters(page, state, search_field, author_field,
                                          filter_chips_row, sort_dropdown,
                                          results_col, stats_text, theme_mode),
    )
    stats_row = ft.Row(
        [stats_text, ft.Container(expand=True), clear_btn],
        vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ----- Results column -------------------------------------------------
    loading_indicator = ft.Column(
        [loading_view("Fetching datasets…", theme_mode)],
        visible=False)
    results_col = ft.Column(spacing=10, expand=True)

    # ----- Filter dialog --------------------------------------------------
    def _open_filter_dialog(e=None):
        _show_filter_dialog(page, state, filter_chips_row, theme_mode,
                            on_apply=lambda: _do_search(
                                page, state, search_field.value, results_col,
                                stats_row, theme_mode, author=author_field.value,
                                sort=sort_dropdown.value,
                            ))

    filter_button = secondary_button(
        "Filters", _open_filter_dialog,
        icon=ft.Icons.FILTER_LIST, theme_mode=theme_mode,
    )

    search_button = ft.ElevatedButton(
        "Search",
        icon=ft.Icons.SEARCH,
        on_click=lambda e: _do_search(page, state, search_field.value,
                                      results_col, stats_row, theme_mode,
                                      author=author_field.value, sort=sort_dropdown.value),
        bgcolor=PRIMARY, color="#1F2937",
        style=ft.ButtonStyle(
            padding=ft.Padding(left=20, right=20, top=10, bottom=10),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    # ----- Quick categories ----------------------------------------------
    quick_categories = ft.Row(
        spacing=8,
        wrap=True,
        controls=[
            ft.Container(
                content=ft.Text(label, size=11, color=text_color(theme_mode)),
                
                border=ft.Border(top=ft.BorderSide(1, ft.Colors.with_opacity(0.15, text_color(theme_mode))), bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.15, text_color(theme_mode))), left=ft.BorderSide(1, ft.Colors.with_opacity(0.15, text_color(theme_mode))), right=ft.BorderSide(1, ft.Colors.with_opacity(0.15, text_color(theme_mode)))),
                border_radius=16,
                ink=True,
                on_click=lambda e, k=key, lbl=label: _quick_filter(
                    page, state, k, lbl, search_field, author_field, sort_dropdown,
                    results_col, stats_row, filter_chips_row, theme_mode,
                ),
                tooltip=f"Show {label}",
            )
            for key, label in [
                ("trending", "🔥 Trending"),
                ("downloads", "⬇ Most Downloaded"),
                ("likes", "👍 Most Liked"),
                ("recent", "🆕 Recently Created"),
                ("text-generation", "Text Generation"),
                ("image-classification", "Image Classification"),
                ("translation", "Translation"),
                ("parquet", "Parquet Format"),
            ]
        ],
    )

    # ----- Layout ---------------------------------------------------------
    search_bar = ft.Row(
        [search_field, search_button],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER)

    secondary_bar = ft.Row(
        [author_field, sort_dropdown, filter_button],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        wrap=True)

    header = section_header(
        "Explore Datasets",
        theme_mode=theme_mode,
        subtitle="Search, filter, and discover datasets from the HuggingFace Hub",
    )

    main_col = ft.Column(
        [
            header,
            ft.Container(height=6),
            search_bar,
            secondary_bar,
            quick_categories,
            filter_chips_row,
            stats_row,
            loading_indicator,
            results_col,
        ],
        spacing=10,
        expand=True)

    # ----- Initial render -------------------------------------------------
    # Defer the initial search to a background thread so the UI paints first.
    # Add a small delay so the page can register the controls before we try to update them.
    def _initial_load():
        import time
        time.sleep(0.3)  # give the page time to register the controls
        _do_search(page, state, state["query"], results_col, stats_row,
                   theme_mode, author=state["author"], sort=state["sort"],
                   initial=True)

    page.run_thread(_initial_load)

    return page_container(main_col, theme_mode=theme_mode)


# --------------------------------------------------------------------------- #
# Search logic
# --------------------------------------------------------------------------- #

def _do_search(page: ft.Page, state: Dict[str, Any], query: str,
               results_col: ft.Column, stats_row: ft.Row, theme_mode: str,
               *, author: str = "", sort: str = "",
               initial: bool = False) -> None:
    """Run the search and update the UI."""
    # Sync state
    state["query"] = (query or "").strip()
    state["author"] = (author or "").strip()
    if sort:
        state["sort"] = sort

    app_state.set(page, "search_query", state["query"])
    app_state.set(page, "search_author", state["author"])
    app_state.set(page, "search_tags", state["tags"])
    app_state.set(page, "selected_sort", state["sort"])

    def _update_ui_safe(controls, *, clear_first=True):
        try:
            if clear_first:
                results_col.controls.clear()
            results_col.controls.extend(controls)
            results_col.update()
        except Exception:
            pass

    def _update_stats_safe(text: str):
        try:
            stats_row.controls[0].value = text
            stats_row.update()
        except Exception:
            pass

    # Show loading
    def _show_loading():
        try:
            results_col.controls.clear()
            results_col.controls.append(loading_view("Fetching datasets…", theme_mode))
            results_col.update()
            stats_row.controls[0].value = "Loading…"
            stats_row.update()
        except Exception:
            pass

    def _run():
        _show_loading()
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            # If a quick filter category was set, route to the right call
            quick = state.pop("_quick_category", None)
            if quick == "recent":
                results = client.get_recent(limit=state["limit"])
            elif quick in ("trending", "downloads", "likes"):
                results = client.list_datasets(
                    search=state["query"],
                    author=state["author"],
                    tags=state["tags"] or None,
                    sort=quick, direction=-1, limit=state["limit"],
                )
            elif quick in ("text-generation", "image-classification",
                           "translation", "parquet"):
                # Add as a tag
                tag_map = {
                    "text-generation": "task_categories:text-generation",
                    "image-classification": "task_categories:image-classification",
                    "translation": "task_categories:translation",
                    "parquet": "format:parquet",
                }
                tags = list(state["tags"])
                if tag_map[quick] not in tags:
                    tags.append(tag_map[quick])
                results = client.list_datasets(
                    search=state["query"],
                    author=state["author"],
                    tags=tags,
                    sort=state["sort"], direction=-1, limit=state["limit"],
                )
            else:
                results = client.list_datasets(
                    search=state["query"],
                    author=state["author"],
                    tags=state["tags"] or None,
                    sort=state["sort"], direction=-1, limit=state["limit"],
                )
            state["results"] = results
            state["total_loaded"] = len(results)
            _render_results(page, state, results, results_col, theme_mode)
            count_text = f"{len(results)} dataset{'s' if len(results) != 1 else ''} found"
            if state["query"]:
                count_text += f" for '{state['query']}'"
            if state["author"]:
                count_text += f" by {state['author']}"
            _update_stats_safe(count_text)
        except HFError as ex:
            _update_ui_safe([error_view(str(ex), theme_mode)])
            _update_stats_safe(f"Error: {ex}")
            show_error(page, str(ex))
        except Exception as ex:
            logger.error("Search error: %s", ex, exc_info=True)
            _update_ui_safe([error_view(str(ex), theme_mode)])
            _update_stats_safe(f"Error: {ex}")

    page.run_thread(_run)


def _render_results(page: ft.Page, state: Dict[str, Any],
                    results: List[Dict[str, Any]],
                    results_col: ft.Column, theme_mode: str) -> None:
    """Render the search results into results_col."""
    try:
        results_col.controls.clear()
        if not results:
            results_col.controls.append(
                empty_view(
                    "No datasets found. Try adjusting your search or filters.",
                    icon=ft.Icons.SEARCH_OFF, theme_mode=theme_mode,
                )
            )
            results_col.update()
            return

        for ds in results:
            is_fav = storage.is_favorite(ds.get("id", ""))
            results_col.controls.append(
                dataset_card(
                    ds,
                    on_open=lambda d=ds: _open_dataset(page, d),
                    on_favorite=lambda d=ds: _toggle_favorite(page, d, results_col,
                                                              state, theme_mode),
                    is_favorite=is_fav,
                    theme_mode=theme_mode,
                )
            )

        # "Load more" button
        if len(results) >= state["limit"]:
            results_col.controls.append(
                ft.Container(
                    padding=10,
                    alignment=ft.Alignment(0, 0),
                    content=secondary_button(
                        "Load more",
                        lambda e: _load_more(page, state, results_col, theme_mode),
                        icon=ft.Icons.EXPAND_MORE, theme_mode=theme_mode,
                    ),
                )
            )

        try:
            results_col.update()
        except Exception:
            # Control may not be added to page yet during initial render
            pass
    except Exception as ex:
        logger.error("Render error: %s", ex, exc_info=True)


def _load_more(page: ft.Page, state: Dict[str, Any],
               results_col: ft.Column, theme_mode: str) -> None:
    """Fetch the next page of results and append."""
    state["offset"] = state.get("offset", 0) + state["limit"]
    state["limit"] = 30

    def _run():
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            results = client.list_datasets(
                search=state["query"],
                author=state["author"],
                tags=state["tags"] or None,
                sort=state["sort"], direction=-1,
                limit=state["limit"], offset=state["offset"],
            )
            state["results"].extend(results)
            _render_results(page, state, state["results"], results_col, theme_mode)
        except HFError as ex:
            show_error(page, str(ex))
        except Exception as ex:
            logger.error("Load more error: %s", ex, exc_info=True)
            show_error(page, str(ex))

    page.run_thread(_run)


def _toggle_favorite(page: ft.Page, dataset: Dict[str, Any],
                     results_col: ft.Column, state: Dict[str, Any],
                     theme_mode: str) -> None:
    new_state = storage.toggle_favorite(dataset)
    if new_state:
        show_success(page, f"Added '{dataset.get('id')}' to favorites")
    else:
        show_success(page, f"Removed '{dataset.get('id')}' from favorites")
    # Re-render to reflect new state
    _render_results(page, state, state.get("results", []), results_col, theme_mode)


def _open_dataset(page: ft.Page, dataset: Dict[str, Any]) -> None:
    from ui.routing import open_dataset_detail
    storage.add_history(dataset)
    open_dataset_detail(page, dataset.get("id"), from_view="explore")


def _clear_filters(page: ft.Page, state: Dict[str, Any],
                   search_field: ft.TextField, author_field: ft.TextField,
                   filter_chips_row: ft.Row, sort_dropdown: ft.Dropdown,
                   results_col: ft.Column, stats_text: ft.Control,
                   theme_mode: str) -> None:
    state["query"] = ""
    state["author"] = ""
    state["tags"] = []
    state["sort"] = "downloads"
    state["offset"] = 0
    search_field.value = ""
    author_field.value = ""
    sort_dropdown.value = "downloads"
    filter_chips_row.controls.clear()
    try:
        search_field.update()
        author_field.update()
        sort_dropdown.update()
        filter_chips_row.update()
    except Exception:
        pass
    _do_search(page, state, "", results_col,
               ft.Row([stats_text]), theme_mode, sort="downloads")


def _quick_filter(page: ft.Page, state: Dict[str, Any], key: str, label: str,
                  search_field: ft.TextField, author_field: ft.TextField,
                  sort_dropdown: ft.Dropdown, results_col: ft.Column,
                  stats_row: ft.Row, filter_chips_row: ft.Row,
                  theme_mode: str) -> None:
    """Handle a quick filter chip click."""
    state["_quick_category"] = key
    # Update sort dropdown if applicable
    if key in ("trending", "downloads"):
        sort_dropdown.value = "downloads"
        try:
            sort_dropdown.update()
        except Exception:
            pass
    elif key == "likes":
        sort_dropdown.value = "likes"
        try:
            sort_dropdown.update()
        except Exception:
            pass
    _do_search(page, state, search_field.value, results_col, stats_row,
               theme_mode, author=author_field.value, sort=sort_dropdown.value)


# --------------------------------------------------------------------------- #
# Filter dialog
# --------------------------------------------------------------------------- #

def _show_filter_dialog(page: ft.Page, state: Dict[str, Any],
                        filter_chips_row: ft.Row, theme_mode: str,
                        *, on_apply) -> None:
    """Open a modal dialog with tag filters."""
    selected = set(state.get("tags", []))

    def _make_chip_group(title: str, options: List[str], color: str) -> ft.Control:
        chips: List[ft.Control] = []
        for opt in options:
            is_on = opt in selected
            chip = ft.Container(
                content=ft.Text(_pretty(opt), size=11,
                                color=color if is_on else text_color(theme_mode),
                                weight=ft.FontWeight.W_600 if is_on else ft.FontWeight.NORMAL),
                padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                border_radius=12,
                border=ft.Border(top=ft.BorderSide(1, color if is_on else ft.Colors.with_opacity(0.2, text_color(theme_mode))), bottom=ft.BorderSide(1, color if is_on else ft.Colors.with_opacity(0.2, text_color(theme_mode))), left=ft.BorderSide(1, color if is_on else ft.Colors.with_opacity(0.2, text_color(theme_mode))), right=ft.BorderSide(1, color if is_on else ft.Colors.with_opacity(0.2, text_color(theme_mode)))),
                bgcolor=ft.Colors.with_opacity(0.12, color) if is_on else None,
                ink=True,
                on_click=lambda e, o=opt, c=color: _toggle_chip(e, o, c),
            )
            chips.append(chip)
        return ft.Column(
            [
                ft.Text(title, size=12, weight=ft.FontWeight.W_600,
                        color=text_color(theme_mode)),
                ft.Row(chips, wrap=True, spacing=6, run_spacing=4),
            ],
            spacing=6, tight=True,
        )

    def _toggle_chip(e, opt: str, color: str):
        if opt in selected:
            selected.discard(opt)
        else:
            selected.add(opt)
        # Re-render dialog content
        _refresh_dialog_content()

    def _refresh_dialog_content():
        try:
            content_col.controls.clear()
            content_col.controls.extend(_build_dialog_content())
            content_col.update()
        except Exception:
            pass

    def _build_dialog_content():
        return [
            _make_chip_group("Task Categories", TASK_CATEGORIES, ACCENT),
            ft.Divider(height=1),
            _make_chip_group("Modalities", MODALITIES, INFO),
            ft.Divider(height=1),
            _make_chip_group("Size Categories", SIZE_CATEGORIES, WARNING),
            ft.Divider(height=1),
            _make_chip_group("Licenses", LICENSES, SUCCESS),
            ft.Divider(height=1),
            _make_chip_group("Formats", FORMATS, PRIMARY),
        ]

    content_col = ft.Column(
        _build_dialog_content(),
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        tight=True,
        height=400)

    def _apply(e):
        state["tags"] = list(selected)
        # Update the chip row above the results
        filter_chips_row.controls.clear()
        for tag in selected:
            filter_chips_row.controls.append(
                ft.Container(
                    content=ft.Text(_pretty(tag), size=10,
                                    color=ACCENT, weight=ft.FontWeight.W_600),
                    padding=ft.Padding(left=6, right=6, top=2, bottom=2),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                )
            )
        try:
            filter_chips_row.update()
        except Exception:
            pass
        dialog.open = False
        try:
            page.overlay.remove(dialog)
        except ValueError:
            pass
        page.update()
        on_apply()

    def _cancel(e):
        dialog.open = False
        try:
            page.overlay.remove(dialog)
        except ValueError:
            pass
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Filter Datasets", weight=ft.FontWeight.BOLD),
        content=content_col,
        actions=[
            ft.TextButton("Cancel", on_click=_cancel),
            ft.ElevatedButton("Apply", on_click=_apply,
                              bgcolor=PRIMARY, color="#1F2937"),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def _pretty(tag: str) -> str:
    from utils.formatters import pretty_tag
    return pretty_tag(tag)
