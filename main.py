"""
HF Dataset Explorer — application entry point.

A desktop application for browsing, analyzing, and comparing datasets
on the HuggingFace Hub. Built with Flet and Python.
"""
from __future__ import annotations

import logging
import os
import sys

import flet as ft

# Ensure local imports work even when run via `python main.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from core import paths  # noqa: F401, E402  (bootstraps app directories)
from core import app_state, storage  # noqa: E402
from ui import navigation, routing  # noqa: E402
from ui.theme import apply_theme  # noqa: E402


def setup_logging() -> None:
    """Configure rotating-file + stderr logging."""
    log_file = paths.logs_dir / "explorer.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                log_file, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )
    # Silence noisy library loggers
    logging.getLogger("flet").setLevel(logging.WARNING)
    logging.getLogger("flet_core").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


import logging.handlers  # noqa: E402

setup_logging()
logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """Flet app entry point."""
    logger.info("Starting HF Dataset Explorer")

    try:
        # --- window / shell ---
        page.title = "HF Dataset Explorer"
        page.window.width = 1400
        page.window.height = 900
        page.window.min_width = 900
        page.window.min_height = 600

        # --- theme ---
        apply_theme(page)
        logger.info("Theme applied")

        # --- state ---
        app_state.init_page_state(page)
        page.mrma_get_view_for_index = None  # placeholder

        # --- build view factory ---
        def apply_settings_callback():
            apply_theme(page)
            if getattr(page, "nav_rail", None) and getattr(page, "content_area", None):
                idx = page.nav_rail.selected_index
                page.content_area.content = page.mrma_get_view_for_index(idx)
                try:
                    page.content_area.update()
                except Exception:
                    pass

        get_view_for_index = routing.make_get_view_for_index(page)
        page.mrma_get_view_for_index = get_view_for_index
        logger.info("View factory created")

        # --- keyboard shortcuts (Ctrl+1..6 to switch tabs) ---
        def _on_keyboard(e: ft.KeyboardEvent):
            rail = getattr(page, "nav_rail", None)
            if rail is None:
                return
            # Don't intercept if a TextField is focused? Flet doesn't expose this easily,
            # so we only intercept Ctrl+digit which is unlikely to clash with text input.
            if (e.ctrl or e.meta) and not e.shift and not e.alt:
                if e.key in "123456":
                    idx = int(e.key) - 1
                    if idx < len(rail.destinations):
                        rail.select(idx)

        page.on_keyboard_event = _on_keyboard

        # --- show the dashboard ---
        navigation.show_main_dashboard(page, get_view_for_index=get_view_for_index)
        logger.info("App started successfully")
    except Exception as ex:
        logger.error("FATAL: App startup failed: %s", ex, exc_info=True)
        # Show a critical error screen
        try:
            page.root = ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR, color="red", size=48),
                    ft.Text("CRITICAL STARTUP ERROR", color="red",
                            size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(str(ex)),
                ], scroll=True),
            )
            page.update()
        except Exception:
            pass


if __name__ == "__main__":
    # ft.run is the modern API (Flet 0.80+); fall back to ft.app for older versions
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(main)
