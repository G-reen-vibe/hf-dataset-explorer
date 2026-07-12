"""Fix Flet border API across the codebase.

Flet 0.85 removed the `ft.border.all()` and `ft.border.only()` helpers.
This script replaces:
- `ft.border.all(W, COLOR)` -> `ft.Border(top=ft.BorderSide(W, COLOR), bottom=ft.BorderSide(W, COLOR), left=ft.BorderSide(W, COLOR), right=ft.BorderSide(W, COLOR))`
- `ft.border.only(bottom=ft.border.BorderSide(W, COLOR))` -> `ft.Border(bottom=ft.BorderSide(W, COLOR))`
- Also handles `ft.border.BorderSide(...)` -> `ft.BorderSide(...)`
"""
from __future__ import annotations

import os
import re


def fix_content(content: str) -> str:
    # First, replace ft.border.BorderSide with ft.BorderSide
    content = content.replace("ft.border.BorderSide", "ft.BorderSide")

    # Replace ft.border.all(W, COLOR) with the explicit Border constructor
    # We need to handle nested parens, so use a function-based regex
    def replace_border_all(match):
        # match.group(1) is the args inside the parens
        args = match.group(1).strip()
        return (f"ft.Border(top=ft.BorderSide({args}), bottom=ft.BorderSide({args}), "
                f"left=ft.BorderSide({args}), right=ft.BorderSide({args}))")

    # Use a non-greedy match for the args
    content = re.sub(
        r"ft\.border\.all\(([^()]+(?:\([^()]*\))?)\)",
        replace_border_all,
        content,
    )

    # Replace ft.border.only(...) with ft.Border(...)
    # This is tricky because we need to keep the kwargs inside
    def replace_border_only(match):
        args = match.group(1).strip()
        return f"ft.Border({args})"

    content = re.sub(
        r"ft\.border\.only\(((?:[^()]|\([^()]*\))*)\)",
        replace_border_only,
        content,
    )

    return content


def main():
    base = "/home/z/my-project/hf-dataset-explorer"
    files = []
    for root, _, fs in os.walk(base):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in fs:
            if f.endswith(".py"):
                files.append(os.path.join(root, f))

    total_changes = 0
    for path in files:
        with open(path) as f:
            original = f.read()
        if "ft.border." not in original:
            continue
        fixed = fix_content(original)
        if fixed != original:
            with open(path, "w") as f:
                f.write(fixed)
            changes = original.count("ft.border.") - fixed.count("ft.border.")
            print(f"  {path}: {changes} replacements")
            total_changes += changes

    print(f"\nTotal replacements: {total_changes}")


if __name__ == "__main__":
    main()
