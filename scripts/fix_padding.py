"""Fix Flet padding API across the codebase."""
from __future__ import annotations

import os
import re


def fix_content(content: str) -> str:
    # Replace ft.padding.all(N) with N (just the number)
    content = re.sub(
        r"ft\.padding\.all\((\d+(?:\.\d+)?)\)",
        r"\1",
        content,
    )
    # Replace ft.padding.symmetric(horizontal=X, vertical=Y) with ft.Padding(left=X, right=X, top=Y, bottom=Y)
    content = re.sub(
        r"ft\.padding\.symmetric\(horizontal=([^,\)]+),\s*vertical=([^,\)]+)\)",
        r"ft.Padding(left=\1, right=\1, top=\2, bottom=\2)",
        content,
    )
    # Also handle reversed order: vertical first, horizontal second
    content = re.sub(
        r"ft\.padding\.symmetric\(vertical=([^,\)]+),\s*horizontal=([^,\)]+)\)",
        r"ft.Padding(left=\2, right=\2, top=\1, bottom=\1)",
        content,
    )
    # Handle horizontal-only
    content = re.sub(
        r"ft\.padding\.symmetric\(horizontal=([^,\)]+)\)",
        r"ft.Padding(left=\1, right=\1)",
        content,
    )
    # Handle vertical-only
    content = re.sub(
        r"ft\.padding\.symmetric\(vertical=([^,\)]+)\)",
        r"ft.Padding(top=\1, bottom=\1)",
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
        if "ft.padding." not in original:
            continue
        fixed = fix_content(original)
        if fixed != original:
            with open(path, "w") as f:
                f.write(fixed)
            changes = original.count("ft.padding.") - fixed.count("ft.padding.")
            print(f"  {path}: {changes} replacements")
            total_changes += changes

    print(f"\nTotal replacements: {total_changes}")


if __name__ == "__main__":
    main()
