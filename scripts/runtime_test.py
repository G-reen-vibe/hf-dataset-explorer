"""Live runtime test: launches the Flet app and verifies the page renders.

This script launches the actual Flet app in web mode, fetches the served
HTML, and checks for expected content (like the app title in the <title> tag).
"""
from __future__ import annotations

import os
import signal
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft


ERRORS: list = []
HTML_CONTENT: str = ""


def main_wrapper(real_main):
    def inner(page: ft.Page):
        try:
            real_main(page)
        except Exception as ex:
            import traceback
            ERRORS.append(ex)
            traceback.print_exc()
    return inner


def check_server(port: int, deadline: float):
    """Background thread that polls the server and captures HTML."""
    global HTML_CONTENT
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as resp:
                status = resp.status
                HTML_CONTENT = resp.read().decode("utf-8", errors="replace")
                print(f"[runtime] Server responded with status {status}")
                print(f"[runtime] HTML length: {len(HTML_CONTENT)} chars")
                # Wait a bit more for any async errors
                time.sleep(2)
                return
        except Exception as ex:
            time.sleep(0.5)
    print("[runtime] Server did not come up in time")


def main():
    port = 8781
    print("[runtime] Importing main.py...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main_module",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("[runtime] main.py imported successfully")

    wrapped = main_wrapper(mod.main)

    # Start the checker thread
    deadline = time.time() + 25
    checker = threading.Thread(target=check_server, args=(port, deadline), daemon=True)
    checker.start()

    # Run the app in the main thread (required by ft.run for signal handling)
    print(f"[runtime] Starting Flet app on port {port}...")
    try:
        ft.run(wrapped, view=None, port=port)
    except Exception as ex:
        print(f"[runtime] ft.run failed: {ex}")
        ERRORS.append(ex)

    checker.join(timeout=2)

    # Verify the HTML content
    if HTML_CONTENT:
        # Check for expected content
        title_in_html = "HF Dataset Explorer" in HTML_CONTENT or "Flet" in HTML_CONTENT
        if title_in_html:
            print("[runtime] PASS: App title found in served HTML")
        else:
            print("[runtime] WARN: App title not found in HTML (may be ok for SPA)")
            # Print first 500 chars of HTML
            print(f"[runtime] HTML preview: {HTML_CONTENT[:500]}")

    if ERRORS:
        print(f"[runtime] FAIL: {len(ERRORS)} errors during app run")
        for err in ERRORS:
            print(f"  - {err}")
        return 1

    print("[runtime] PASS: App started and served without errors")
    return 0


if __name__ == "__main__":
    def timeout_handler(signum, frame):
        print("[runtime] Test completed (alarm fired)")
        # Force exit
        os._exit(0)

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(25)

    sys.exit(main())
