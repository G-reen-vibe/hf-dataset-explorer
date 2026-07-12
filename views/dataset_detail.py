"""Dataset detail view: shows full metadata, statistics, splits, files, and rows."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from api.hf_client import HFError, get_client
from core import storage
from ui.theme import effective_theme_mode
from utils.formatters import (
    format_bytes,
    format_compact,
    format_date,
    format_int,
    format_relative_date,
    pretty_tag,
    strip_markdown,
    truncate,
)
from api.hf_client import parse_tags
from utils.ui_helpers import (
    ACCENT,
    ACCENT_LIGHT,
    INFO,
    PRIMARY,
    PRIMARY_DARK,
    SUCCESS,
    WARNING,
    DANGER,
    border_color,
    empty_view,
    error_view,
    loading_view,
    muted_text_color,
    page_container,
    primary_button,
    secondary_button,
    section_header,
    show_error,
    show_success,
    stat_chip,
    stat_tile,
    surface_bg,
    tag_chip,
    tag_row,
    text_color,
)

logger = logging.getLogger(__name__)


def get_dataset_detail_view(page: ft.Page, dataset_id: str,
                            on_back: Optional[Callable] = None) -> ft.Control:
    theme_mode = effective_theme_mode(page)

    state = {
        "dataset_id": dataset_id,
        "dataset": None,
        "parquet_listing": None,
        "rows_data": None,
        "active_config": None,
        "active_split": None,
        "loading_rows": False,
        "rows_offset": 0,
        "rows_length": 20,
    }

    # ----- Header ---------------------------------------------------------
    back_btn = ft.TextButton(
        "← Back",
        on_click=lambda e: on_back() if on_back else None,
        icon=ft.Icons.ARROW_BACK,
    )

    favorite_btn = ft.OutlinedButton(
        "Favorite",
        icon=ft.Icons.FAVORITE_BORDER,
        on_click=lambda e: _toggle_favorite(page, state, header_actions, theme_mode),
    )

    open_in_browser_btn = ft.OutlinedButton(
        "Open on HF",
        icon=ft.Icons.OPEN_IN_NEW,
        on_click=lambda e: page.launch_url(f"https://huggingface.co/datasets/{dataset_id}"),
    )

    header_actions = ft.Row(
        [back_btn, favorite_btn, open_in_browser_btn],
        spacing=8, wrap=True)

    # ----- Loading placeholder -------------------------------------------
    loading_col = ft.Column([loading_view("Loading dataset…", theme_mode)],
                             expand=True)

    # ----- Main content column (filled in once data arrives) -------------
    content_col = ft.Column(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
    content_col.controls.append(loading_col)

    # ----- Layout ---------------------------------------------------------
    header = ft.Column(
        [
            header_actions,
            ft.Text(
                dataset_id,
                size=24, weight=ft.FontWeight.BOLD,
                color=text_color(theme_mode),
                selectable=True,
            ),
        ],
        spacing=8,
    )

    main_col = ft.Column(
        [header, content_col],
        spacing=16,
        expand=True)

    # ----- Async fetch ----------------------------------------------------
    def _fetch():
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            dataset = client.get_dataset(dataset_id)
            state["dataset"] = dataset
            # Try parquet listing
            try:
                parquet_listing = client.get_parquet_listing(dataset_id)
                state["parquet_listing"] = parquet_listing
                # Pick first config/split as default
                if parquet_listing and isinstance(parquet_listing, dict):
                    first_config = next(iter(parquet_listing.keys()), None)
                    if first_config:
                        state["active_config"] = first_config
                        splits = parquet_listing[first_config]
                        if isinstance(splits, dict):
                            first_split = next(iter(splits.keys()), None)
                            if first_split:
                                state["active_split"] = first_split
            except HFError as ex:
                logger.info("No parquet listing for %s: %s", dataset_id, ex)
                state["parquet_listing"] = None

            # Build the full UI
            content_col.controls.clear()
            content_col.controls.extend(_build_content(page, state, theme_mode))
            try:
                content_col.update()
            except Exception:
                pass

            # Update favorite button state
            _update_favorite_button(state, favorite_btn)
            try:
                favorite_btn.update()
            except Exception:
                pass

            # Preload first split rows in the background
            if state["active_config"] and state["active_split"]:
                page.run_thread(_fetch_rows, state, content_col, theme_mode, page)

        except HFError as ex:
            content_col.controls.clear()
            content_col.controls.append(error_view(str(ex), theme_mode))
            try:
                content_col.update()
            except Exception:
                pass
            show_error(page, str(ex))
        except Exception as ex:
            logger.error("Detail fetch error: %s", ex, exc_info=True)
            content_col.controls.clear()
            content_col.controls.append(error_view(str(ex), theme_mode))
            try:
                content_col.update()
            except Exception:
                pass

    def _fetch_rows(state, content_col, theme_mode, page):
        """Fetch rows for the active split."""
        state["loading_rows"] = True
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            rows_data = client.get_rows(
                state["dataset_id"],
                state["active_config"],
                state["active_split"],
                offset=state["rows_offset"],
                length=state["rows_length"],
            )
            state["rows_data"] = rows_data
            # Re-render rows section
            _render_rows_section(page, state, content_col, theme_mode)
        except HFError as ex:
            state["rows_data"] = {"error": str(ex)}
            _render_rows_section(page, state, content_col, theme_mode)
        except Exception as ex:
            logger.error("Rows fetch error: %s", ex, exc_info=True)
            state["rows_data"] = {"error": str(ex)}
            _render_rows_section(page, state, content_col, theme_mode)
        finally:
            state["loading_rows"] = False

    page.run_thread(_fetch)

    return page_container(main_col, theme_mode=theme_mode)


# --------------------------------------------------------------------------- #
# Content builders
# --------------------------------------------------------------------------- #

def _build_content(page: ft.Page, state: Dict[str, Any], theme_mode: str) -> List[ft.Control]:
    """Build the full detail content."""
    dataset = state["dataset"]
    if not dataset:
        return [empty_view("No dataset data", theme_mode=theme_mode)]

    # Stats overview
    stats_overview = _build_stats_overview(dataset, theme_mode)

    # Tag overview
    tags = dataset.get("tags", []) or []
    tag_overview = _build_section(
        "Tags & Categories",
        tag_row(tags, theme_mode=theme_mode, max_tags=20),
        theme_mode,
    )

    # Card data (features, splits, sizes)
    card_data_section = _build_card_data_section(dataset, theme_mode)

    # Files (siblings)
    files_section = _build_files_section(dataset, theme_mode)

    # Description / card content
    description_section = _build_description_section(dataset, theme_mode)

    # Dataset viewer (rows)
    viewer_section = _build_viewer_section(page, state, theme_mode)

    return [
        stats_overview,
        tag_overview,
        card_data_section,
        description_section,
        viewer_section,
        files_section,
    ]


def _build_stats_overview(dataset: Dict[str, Any], theme_mode: str) -> ft.Control:
    """Top stat tiles for the dataset."""
    from utils.formatters import get_dataset_stats
    stats = get_dataset_stats(dataset)
    return ft.Column(
        [
            section_header("Statistics", theme_mode=theme_mode),
            ft.Row(
                [
                    stat_tile("Downloads", format_int(stats["downloads"]),
                              hint="All-time downloads",
                              icon=ft.Icons.DOWNLOAD, color=INFO,
                              theme_mode=theme_mode),
                    stat_tile("Likes", format_int(stats["likes"]),
                              hint="Community likes",
                              icon=ft.Icons.THUMB_UP, color=WARNING,
                              theme_mode=theme_mode),
                    stat_tile("Trending", format_compact(stats["trendingScore"]),
                              hint="Trending score",
                              icon=ft.Icons.TRENDING_UP, color=SUCCESS,
                              theme_mode=theme_mode),
                    stat_tile("Examples", format_int(stats["total_examples"]),
                              hint="Across all splits",
                              icon=ft.Icons.LIST_ALT, color=ACCENT,
                              theme_mode=theme_mode),
                ],
                spacing=10, wrap=True, run_spacing=10,
            ),
            ft.Row(
                [
                    stat_tile("Download Size", format_bytes(stats["download_size"]),
                              hint="Compressed size",
                              icon=ft.Icons.COMPRESS, color=ACCENT_LIGHT,
                              theme_mode=theme_mode),
                    stat_tile("Dataset Size", format_bytes(stats["dataset_size"]),
                              hint="Uncompressed size",
                              icon=ft.Icons.STORAGE, color=PRIMARY_DARK,
                              theme_mode=theme_mode),
                    stat_tile("Configs", format_int(len(stats["configs"]) or 1),
                              hint="Configurations",
                              icon=ft.Icons.SETTINGS_INPUT_COMPONENT,
                              color=INFO, theme_mode=theme_mode),
                    stat_tile("Splits", format_int(len(stats["splits"])),
                              hint="Data splits",
                              icon=ft.Icons.CALL_SPLIT, color=SUCCESS,
                              theme_mode=theme_mode),
                ],
                spacing=10, wrap=True, run_spacing=10,
            ),
            ft.Container(
                
                border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
                border_radius=8,
                bgcolor=surface_bg(theme_mode),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.UPDATE, size=14,
                                color=muted_text_color(theme_mode)),
                        ft.Text(
                            f"Last modified: {format_date(dataset.get('lastModified'))} "
                            f"({format_relative_date(dataset.get('lastModified'))})",
                            size=11, color=muted_text_color(theme_mode),
                        ),
                        ft.Container(width=20),
                        ft.Icon(ft.Icons.CALENDAR_TODAY, size=14,
                                color=muted_text_color(theme_mode)),
                        ft.Text(
                            f"Created: {format_date(dataset.get('createdAt'))}",
                            size=11, color=muted_text_color(theme_mode),
                        ),
                    ],
                    wrap=True, spacing=4,
                ),
            ),
        ],
        spacing=8,
    )


def _build_section(title: str, content: ft.Control, theme_mode: str,
                   subtitle: Optional[str] = None) -> ft.Control:
    return ft.Column(
        [
            section_header(title, theme_mode=theme_mode, subtitle=subtitle),
            content,
        ],
        spacing=8)


def _build_card_data_section(dataset: Dict[str, Any], theme_mode: str) -> ft.Control:
    """Show features, splits, and configs from cardData."""
    card_data = dataset.get("cardData") or {}
    dataset_info = card_data.get("dataset_info") or {}
    splits = dataset_info.get("splits") or []
    features = dataset_info.get("features") or []
    configs = card_data.get("configs") or []

    sections: List[ft.Control] = [section_header("Schema & Splits", theme_mode=theme_mode)]

    # Features table
    if features:
        feature_rows = [ft.DataRow(
            cells=[
                ft.DataCell(ft.Text("Feature", size=11, weight=ft.FontWeight.BOLD,
                                    color=muted_text_color(theme_mode))),
                ft.DataCell(ft.Text("Type", size=11, weight=ft.FontWeight.BOLD,
                                    color=muted_text_color(theme_mode))),
            ],
        )]
        for feat in features:
            name = feat.get("name", "?")
            dtype = feat.get("dtype", "—")
            if feat.get("_type") == "Sequence":
                dtype = f"Sequence[{feat.get('feature', {}).get('dtype', '?')}]"
            elif feat.get("_type") == "List":
                dtype = f"List[{feat.get('feature', {}).get('dtype', '?')}]"
            feature_rows.append(ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(name, size=12, color=text_color(theme_mode),
                                        selectable=True)),
                    ft.DataCell(ft.Container(
                        padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.1, INFO),
                        content=ft.Text(dtype, size=11, color=INFO,
                                        weight=ft.FontWeight.W_500),
                    )),
                ],
            ))
        features_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Feature", size=11,
                                      color=muted_text_color(theme_mode))),
                ft.DataColumn(ft.Text("Type", size=11,
                                      color=muted_text_color(theme_mode))),
            ],
            rows=feature_rows[1:],  # skip the header row we added
            horizontal_lines=ft.BorderSide(1, border_color(theme_mode)),
            heading_row_height=36,
            data_row_min_height=32,
            column_spacing=20,
            divider_thickness=0,
        )
        sections.append(features_table)
    else:
        sections.append(ft.Text("No feature schema available.",
                                size=12, color=muted_text_color(theme_mode)))

    # Splits table
    if splits:
        sections.append(ft.Container(height=8))
        sections.append(ft.Text("Splits", size=13, weight=ft.FontWeight.W_600,
                                color=text_color(theme_mode)))
        split_rows = []
        for sp in splits:
            name = sp.get("name", "?")
            examples = sp.get("num_examples", 0)
            bytes_size = sp.get("num_bytes", 0)
            split_rows.append(ft.DataRow(
                cells=[
                    ft.DataCell(ft.Container(
                        padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.1, SUCCESS),
                        content=ft.Text(name, size=11, color=SUCCESS,
                                        weight=ft.FontWeight.W_500),
                    )),
                    ft.DataCell(ft.Text(format_int(examples), size=12,
                                        color=text_color(theme_mode))),
                    ft.DataCell(ft.Text(format_bytes(bytes_size), size=12,
                                        color=text_color(theme_mode))),
                ],
            ))
        splits_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Split", size=11, color=muted_text_color(theme_mode))),
                ft.DataColumn(ft.Text("Examples", size=11, color=muted_text_color(theme_mode))),
                ft.DataColumn(ft.Text("Size", size=11, color=muted_text_color(theme_mode))),
            ],
            rows=split_rows,
            horizontal_lines=ft.BorderSide(1, border_color(theme_mode)),
            heading_row_height=36,
            data_row_min_height=32,
            column_spacing=20,
        )
        sections.append(splits_table)

    # Configs
    if configs:
        sections.append(ft.Container(height=8))
        sections.append(ft.Text("Configurations", size=13,
                                weight=ft.FontWeight.W_600,
                                color=text_color(theme_mode)))
        config_chips = []
        for cfg in configs:
            name = cfg.get("config_name", cfg.get("name", "?"))
            config_chips.append(tag_chip(name, color=ACCENT, theme_mode=theme_mode))
        sections.append(ft.Row(config_chips, wrap=True, spacing=6, run_spacing=4))

    return ft.Column(sections, spacing=6)


def _build_description_section(dataset: Dict[str, Any], theme_mode: str) -> ft.Control:
    description = dataset.get("description") or ""
    if not description:
        return _build_section(
            "Description",
            ft.Text("No description available.", size=12,
                    color=muted_text_color(theme_mode)),
            theme_mode,
        )
    cleaned = strip_markdown(description)
    # Truncate for display; full text in a tooltip / expandable section
    is_long = len(cleaned) > 600
    preview = cleaned[:600] + ("…" if is_long else "")

    desc_text = ft.Text(
        preview,
        size=13, color=text_color(theme_mode),
        selectable=True,
    )

    def _toggle(e):
        if desc_text.value == preview:
            desc_text.value = cleaned
            toggle_btn.text = "Show less"
        else:
            desc_text.value = preview
            toggle_btn.text = "Show more"
        try:
            desc_text.update()
            toggle_btn.update()
        except Exception:
            pass

    toggle_btn = ft.TextButton(
        "Show more" if is_long else "",
        on_click=_toggle,
        visible=is_long,
    )

    return _build_section(
        "Description",
        ft.Column([desc_text, toggle_btn], spacing=4),
        theme_mode,
    )


def _build_files_section(dataset: Dict[str, Any], theme_mode: str) -> ft.Control:
    siblings = dataset.get("siblings") or []
    if not siblings:
        return _build_section(
            "Files",
            ft.Text("No file listing available.", size=12,
                    color=muted_text_color(theme_mode)),
            theme_mode,
        )
    # Show up to 50 files
    files = siblings[:50]
    rows = []
    for sib in files:
        rfilename = sib.get("rfilename", "?")
        size = sib.get("size", 0) or 0
        # Determine icon based on extension
        ext = rfilename.rsplit(".", 1)[-1].lower() if "." in rfilename else ""
        icon = {
            "parquet": ft.Icons.TABLE_VIEW,
            "json": ft.Icons.CODE,
            "csv": ft.Icons.TABLE_CHART,
            "md": ft.Icons.ARTICLE,
            "txt": ft.Icons.ARTICLE,
            "png": ft.Icons.IMAGE,
            "jpg": ft.Icons.IMAGE,
            "jpeg": ft.Icons.IMAGE,
            "wav": ft.Icons.AUDIO_FILE,
            "mp3": ft.Icons.AUDIO_FILE,
            "mp4": ft.Icons.VIDEO_FILE,
            "gitattributes": ft.Icons.SETTINGS,
        }.get(ext, ft.Icons.INSERT_DRIVE_FILE)
        rows.append(ft.DataRow(
            cells=[
                ft.DataCell(ft.Row([
                    ft.Icon(icon, size=14, color=muted_text_color(theme_mode)),
                    ft.Text(rfilename, size=11, color=text_color(theme_mode),
                            selectable=True, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=6)),
                ft.DataCell(ft.Text(format_bytes(size) if size else "—", size=11,
                                    color=muted_text_color(theme_mode))),
            ],
        ))

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("File", size=11, color=muted_text_color(theme_mode))),
            ft.DataColumn(ft.Text("Size", size=11, color=muted_text_color(theme_mode))),
        ],
        rows=rows,
        horizontal_lines=ft.BorderSide(1, border_color(theme_mode)),
        heading_row_height=36,
        data_row_min_height=32,
        column_spacing=20,
    )

    note = ft.Text(
        f"Showing {len(files)} of {len(siblings)} files",
        size=11, color=muted_text_color(theme_mode),
    )

    return _build_section("Files", ft.Column([table, note], spacing=4), theme_mode)


# --------------------------------------------------------------------------- #
# Dataset viewer (rows preview)
# --------------------------------------------------------------------------- #

def _build_viewer_section(page: ft.Page, state: Dict[str, Any],
                          theme_mode: str) -> ft.Control:
    """Build the dataset viewer with config/split selectors and rows table."""
    parquet_listing = state.get("parquet_listing")

    # Config / split dropdowns
    config_options = []
    split_options = []
    if parquet_listing and isinstance(parquet_listing, dict):
        config_options = list(parquet_listing.keys())
        if state["active_config"] in parquet_listing:
            splits_dict = parquet_listing[state["active_config"]]
            if isinstance(splits_dict, dict):
                split_options = list(splits_dict.keys())

    config_dd = ft.Dropdown(
        label="Config",
        value=state["active_config"],
        options=[ft.dropdown.Option(c) for c in config_options],
        dense=True, border_radius=8, text_size=12,
        border_color=border_color(theme_mode),
        width=200,
        on_select=lambda e: _on_config_change(page, state, e.control.value,
                                              viewer_content, theme_mode),
    )
    split_dd = ft.Dropdown(
        label="Split",
        value=state["active_split"],
        options=[ft.dropdown.Option(s) for s in split_options],
        dense=True, border_radius=8, text_size=12,
        border_color=border_color(theme_mode),
        width=200,
        on_select=lambda e: _on_split_change(page, state, e.control.value,
                                             viewer_content, theme_mode),
    )

    rows_per_page = ft.Dropdown(
        label="Rows",
        value=str(state["rows_length"]),
        options=[ft.dropdown.Option("10"), ft.dropdown.Option("20"),
                 ft.dropdown.Option("50"), ft.dropdown.Option("100")],
        dense=True, border_radius=8, text_size=12,
        border_color=border_color(theme_mode),
        width=120,
        on_select=lambda e: _on_rows_per_page_change(page, state, int(e.control.value),
                                                     viewer_content, theme_mode),
    )

    viewer_content = ft.Column(spacing=10, expand=True)

    header = section_header(
        "Dataset Viewer",
        theme_mode=theme_mode,
        subtitle="Preview rows from the dataset (via the HuggingFace Rows API)",
    )

    selectors = ft.Row(
        [config_dd, split_dd, rows_per_page],
        spacing=8, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    pagination_row = ft.Row(
        [
            ft.Text("Page 1", size=11, color=muted_text_color(theme_mode),
                    ref=None),
            ft.Container(expand=True),
            secondary_button("Previous", lambda e: _prev_page(page, state, viewer_content,
                                                                theme_mode),
                             icon=ft.Icons.CHEVRON_LEFT, theme_mode=theme_mode),
            secondary_button("Next", lambda e: _next_page(page, state, viewer_content,
                                                           theme_mode),
                             icon=ft.Icons.CHEVRON_RIGHT, theme_mode=theme_mode),
        ],
        spacing=8,
    )
    state["pagination_row"] = pagination_row

    # Initial placeholder while rows load
    viewer_content.controls.append(loading_view("Loading rows…", theme_mode))

    return ft.Column(
        [
            header,
            selectors,
            viewer_content,
            pagination_row,
        ],
        spacing=10)


def _on_config_change(page: ft.Page, state: Dict[str, Any], new_config: str,
                      viewer_content: ft.Column, theme_mode: str) -> None:
    state["active_config"] = new_config
    state["active_split"] = None
    state["rows_offset"] = 0
    state["rows_data"] = None
    # Reset split dropdown based on new config
    parquet_listing = state.get("parquet_listing", {})
    splits = list(parquet_listing.get(new_config, {}).keys()) if parquet_listing else []
    if splits:
        state["active_split"] = splits[0]
    # Update split dropdown UI
    # Find the dropdown in the parent row
    _rebuild_viewer(page, state, viewer_content, theme_mode)


def _on_split_change(page: ft.Page, state: Dict[str, Any], new_split: str,
                     viewer_content: ft.Column, theme_mode: str) -> None:
    state["active_split"] = new_split
    state["rows_offset"] = 0
    state["rows_data"] = None
    _refetch_rows(page, state, viewer_content, theme_mode)


def _on_rows_per_page_change(page: ft.Page, state: Dict[str, Any], new_length: int,
                             viewer_content: ft.Column, theme_mode: str) -> None:
    state["rows_length"] = new_length
    state["rows_offset"] = 0
    _refetch_rows(page, state, viewer_content, theme_mode)


def _prev_page(page: ft.Page, state: Dict[str, Any], viewer_content: ft.Column,
               theme_mode: str) -> None:
    if state["rows_offset"] > 0:
        state["rows_offset"] = max(0, state["rows_offset"] - state["rows_length"])
        _refetch_rows(page, state, viewer_content, theme_mode)


def _next_page(page: ft.Page, state: Dict[str, Any], viewer_content: ft.Column,
               theme_mode: str) -> None:
    state["rows_offset"] += state["rows_length"]
    _refetch_rows(page, state, viewer_content, theme_mode)


def _refetch_rows(page: ft.Page, state: Dict[str, Any], viewer_content: ft.Column,
                  theme_mode: str) -> None:
    if not state["active_config"] or not state["active_split"]:
        return
    state["rows_data"] = None
    viewer_content.controls.clear()
    viewer_content.controls.append(loading_view("Loading rows…", theme_mode))
    try:
        viewer_content.update()
    except Exception:
        pass

    def _run():
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            rows_data = client.get_rows(
                state["dataset_id"], state["active_config"], state["active_split"],
                offset=state["rows_offset"], length=state["rows_length"],
            )
            state["rows_data"] = rows_data
        except HFError as ex:
            state["rows_data"] = {"error": str(ex)}
        except Exception as ex:
            logger.error("Rows fetch error: %s", ex, exc_info=True)
            state["rows_data"] = {"error": str(ex)}
        _render_rows_section(page, state, viewer_content, theme_mode)

    page.run_thread(_run)


def _rebuild_viewer(page: ft.Page, state: Dict[str, Any], viewer_content: ft.Column,
                    theme_mode: str) -> None:
    """Rebuild the entire viewer (used when config changes)."""
    # Find the parent column containing the viewer
    # Just re-fetch rows
    _refetch_rows(page, state, viewer_content, theme_mode)


def _render_rows_section(page: ft.Page, state: Dict[str, Any],
                         viewer_content: ft.Column, theme_mode: str) -> None:
    """Render the rows table into viewer_content."""
    try:
        viewer_content.controls.clear()

        rows_data = state.get("rows_data")
        if not rows_data:
            viewer_content.controls.append(loading_view("Loading rows…", theme_mode))
            try:
                viewer_content.update()
            except Exception:
                pass
            return

        if isinstance(rows_data, dict) and "error" in rows_data:
            viewer_content.controls.append(
                empty_view(
                    rows_data["error"],
                    icon=ft.Icons.ERROR_OUTLINE, theme_mode=theme_mode,
                )
            )
            try:
                viewer_content.update()
            except Exception:
                pass
            return

        features = rows_data.get("features") or []
        rows = rows_data.get("rows") or []

        if not rows:
            viewer_content.controls.append(
                empty_view("No rows in this split.",
                           icon=ft.Icons.TABLE_ROWS, theme_mode=theme_mode)
            )
            try:
                viewer_content.update()
            except Exception:
                pass
            return

        # Build columns from features
        num_columns = len(features)
        # Limit columns shown to avoid insane widths
        max_cols = 8
        show_features = features[:max_cols]
        hidden_count = max(0, num_columns - max_cols)

        columns = []
        for feat in show_features:
            name = feat.get("name", "?")
            columns.append(ft.DataColumn(
                ft.Text(name, size=11, weight=ft.FontWeight.W_600,
                        color=muted_text_color(theme_mode)),
            ))

        data_rows = []
        for row in rows:
            row_obj = row.get("row", {}) if isinstance(row, dict) else {}
            cells = []
            for feat in show_features:
                feat_name = feat.get("name", "")
                value = row_obj.get(feat_name, "")
                cell_text = _format_cell_value(value, feat)
                cells.append(ft.DataCell(cell_text))
            data_rows.append(ft.DataRow(cells=cells))

        table = ft.DataTable(
            columns=columns,
            rows=data_rows,
            horizontal_lines=ft.BorderSide(1, border_color(theme_mode)),
            heading_row_height=36,
            data_row_min_height=36,
            column_spacing=16,
            divider_thickness=0,
        )

        viewer_content.controls.append(ft.Container(
            border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
            border_radius=8,
            padding=8,
            bgcolor=surface_bg(theme_mode),
            content=ft.Column(
                [table] + (
                    [ft.Text(f"+{hidden_count} more columns not shown",
                             size=10, color=muted_text_color(theme_mode))]
                    if hidden_count > 0 else []
                ),
                spacing=6, scroll=ft.ScrollMode.AUTO,
            ),
        ))

        # Update pagination text
        try:
            pagination_row = state.get("pagination_row")
            if pagination_row:
                offset = state["rows_offset"]
                length = state["rows_length"]
                total = rows_data.get("num_rows_total") or rows_data.get("total") or "?"
                end = offset + len(rows)
                pagination_row.controls[0].value = f"Showing {offset + 1}–{end} of {total}"
                pagination_row.update()
        except Exception:
            pass

        try:
            viewer_content.update()
        except Exception:
            pass

    except Exception as ex:
        logger.error("Render rows error: %s", ex, exc_info=True)


def _format_cell_value(value: Any, feat: Dict[str, Any]) -> ft.Control:
    """Format a cell value for display in the rows table."""
    if value is None:
        return ft.Text("—", size=11, color=muted_text_color("dark"),
                       italic=True)
    feat_type = feat.get("_type", "")
    dtype = feat.get("dtype", "")

    # String values
    if isinstance(value, str):
        # Long strings: truncate
        if len(value) > 200:
            return ft.Text(value[:200] + "…", size=11, selectable=True,
                           max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
        return ft.Text(value, size=11, selectable=True,
                       max_lines=5, overflow=ft.TextOverflow.ELLIPSIS)

    # Numbers
    if isinstance(value, (int, float)):
        if isinstance(value, int) and abs(value) > 1_000_000:
            return ft.Text(format_compact(value), size=11, color=INFO)
        return ft.Text(str(value), size=11)

    # Lists / dicts
    if isinstance(value, (list, dict)):
        import json
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
        if len(text) > 200:
            text = text[:200] + "…"
        return ft.Text(text, size=10, font_family="Consolas", selectable=True,
                       max_lines=5, overflow=ft.TextOverflow.ELLIPSIS)

    return ft.Text(str(value), size=11, selectable=True)


# --------------------------------------------------------------------------- #
# Favorite toggle
# --------------------------------------------------------------------------- #

def _toggle_favorite(page: ft.Page, state: Dict[str, Any],
                     header_actions: ft.Row, theme_mode: str) -> None:
    dataset = state.get("dataset")
    if not dataset:
        return
    new_state = storage.toggle_favorite(dataset)
    if new_state:
        show_success(page, f"Added '{dataset.get('id')}' to favorites")
    else:
        show_success(page, f"Removed '{dataset.get('id')}' from favorites")
    # Update the button
    for ctrl in header_actions.controls:
        if isinstance(ctrl, ft.OutlinedButton) and "Favorite" in (ctrl.text or ""):
            ctrl.icon = ft.Icons.FAVORITE if new_state else ft.Icons.FAVORITE_BORDER
            ctrl.text = "Favorited" if new_state else "Favorite"
            try:
                ctrl.update()
            except Exception:
                pass
            break


def _update_favorite_button(state: Dict[str, Any], btn: ft.OutlinedButton) -> None:
    dataset = state.get("dataset")
    if not dataset:
        return
    is_fav = storage.is_favorite(dataset.get("id", ""))
    btn.icon = ft.Icons.FAVORITE if is_fav else ft.Icons.FAVORITE_BORDER
    btn.text = "Favorited" if is_fav else "Favorite"
