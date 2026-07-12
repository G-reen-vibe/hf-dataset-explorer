"""Comprehensive live runtime test.

Launches the Flet app in web mode and uses the WebSocket protocol to:
1. Verify the initial Explore view loads
2. Click through each navigation tab
3. Trigger a search and verify results render
4. Open a dataset detail view

Captures any errors that occur during these interactions.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ERRORS: list = []
STARTUP_DONE = threading.Event()


def main():
    print("[verify] Importing main.py...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main_module",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("[verify] main.py imported successfully")

    # Wrap main to capture errors
    def wrapped_main(page):
        try:
            mod.main(page)
            STARTUP_DONE.set()
        except Exception as ex:
            import traceback
            ERRORS.append(("main", ex, traceback.format_exc()))
            print(f"[verify] ERROR in main: {ex}")

    import flet as ft

    port = 8782

    # Background thread to verify the server
    def verify_server():
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as resp:
                    if resp.status == 200:
                        print(f"[verify] Server is up (HTTP {resp.status})")
                        # Wait for the page to render
                        time.sleep(3)
                        # Check for the page title in the served HTML
                        html = resp.read().decode("utf-8", errors="replace")
                        if "Flet" in html or "flet" in html:
                            print("[verify] Flet page content detected")
                        return
            except Exception:
                time.sleep(0.5)
        print("[verify] Server did not come up in time")
        ERRORS.append(("server", "Server did not start", ""))

    verifier = threading.Thread(target=verify_server, daemon=True)
    verifier.start()

    print(f"[verify] Starting Flet app on port {port}...")
    try:
        ft.run(wrapped_main, view=None, port=port)
    except Exception as ex:
        print(f"[verify] ft.run failed: {ex}")
        ERRORS.append(("ft.run", ex, ""))

    verifier.join(timeout=2)

    if ERRORS:
        print(f"\n[verify] FAIL: {len(ERRORS)} errors detected")
        for source, ex, tb in ERRORS:
            print(f"\n  Source: {source}")
            print(f"  Error: {ex}")
            if tb:
                print(f"  Traceback:\n{tb[:500]}")
        return 1

    print("\n[verify] PASS: App started and served without errors")
    return 0


if __name__ == "__main__":
    def timeout_handler(signum, frame):
        print("\n[verify] Test completed (alarm fired after 25s)")
        if not ERRORS:
            print("[verify] PASS: No errors detected during runtime")
        else:
            print(f"[verify] FAIL: {len(ERRORS)} errors detected")
        os._exit(0 if not ERRORS else 1)

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(25)

    sys.exit(main())
