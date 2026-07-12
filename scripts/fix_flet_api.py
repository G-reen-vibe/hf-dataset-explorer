"""Fix Flet 0.85 API: replace on_change with on_select in Dropdown calls.

Uses a simpler approach: find `ft.Dropdown(` blocks and replace `on_change=`
with `on_select=` within them. Handles multi-line calls with nested parens.
"""
from __future__ import annotations

import os
import re


def find_matching_paren(text: str, start: int) -> int:
    """Find the closing paren that matches the opening paren at `start`."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def fix_dropdown_calls(content: str) -> str:
    """Find every ft.Dropdown(...) call and replace on_change with on_select inside."""
    result = []
    i = 0
    while i < len(content):
        # Find the next "ft.Dropdown(" occurrence
        idx = content.find("ft.Dropdown(", i)
        if idx == -1:
            result.append(content[i:])
            break
        # Append everything before this match
        result.append(content[i:idx])
        # Find the matching closing paren
        open_paren = idx + len("ft.Dropdown")  # position of "("
        close_paren = find_matching_paren(content, open_paren)
        if close_paren == -1:
            # Unbalanced; just append the rest
            result.append(content[idx:])
            break
        # Extract the call
        call_text = content[idx:close_paren + 1]
        # Replace on_change= with on_select= inside this call
        fixed_call = re.sub(r"\bon_change=", "on_select=", call_text)
        result.append(fixed_call)
        i = close_paren + 1
    return "".join(result)


def remove_padding_from_column_row(content: str) -> str:
    """Remove padding= arg from ft.Column(...) and ft.Row(...) calls."""
    for ctrl_name in ("Column", "Row"):
        marker = f"ft.{ctrl_name}("
        result = []
        i = 0
        while i < len(content):
            idx = content.find(marker, i)
            if idx == -1:
                result.append(content[i:])
                break
            result.append(content[i:idx])
            open_paren = idx + len(marker) - 1
            close_paren = find_matching_paren(content, open_paren)
            if close_paren == -1:
                result.append(content[idx:])
                break
            call_text = content[idx:close_paren + 1]
            # Remove padding=<value> where value is int, None, or Padding(...)
            # First try to remove "padding=ft.Padding(...)" - need to find matching paren
            def remove_padding(s):
                # Find padding=ft.Padding( and remove until matching )
                pad_marker = "padding=ft.Padding("
                idx2 = s.find(pad_marker)
                if idx2 != -1:
                    open2 = idx2 + len(pad_marker) - 1
                    close2 = find_matching_paren(s, open2)
                    if close2 != -1:
                        # Remove from idx2 to close2+1, plus possible trailing comma+space
                        end = close2 + 1
                        if end < len(s) and s[end:end+2] == ", ":
                            end += 2
                        elif end < len(s) and s[end] == ",":
                            end += 1
                        return s[:idx2] + s[end:]
                # Try padding=int or padding=None
                s = re.sub(r"padding=(\d+|None),?\s*", "", s)
                return s
            fixed_call = remove_padding(call_text)
            result.append(fixed_call)
            i = close_paren + 1
        content = "".join(result)
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
        if "ft.Dropdown(" not in original and "ft.Column(" not in original and "ft.Row(" not in original:
            continue
        fixed = fix_dropdown_calls(original)
        fixed = remove_padding_from_column_row(fixed)
        if fixed != original:
            with open(path, "w") as f:
                f.write(fixed)
            dropdown_changes = original.count("on_change=") - fixed.count("on_change=")
            print(f"  {path}: {dropdown_changes} on_change -> on_select")
            total_changes += dropdown_changes

    print(f"\nTotal changes: {total_changes}")


if __name__ == "__main__":
    main()
