"""Formatting helpers for numbers, sizes, dates, and tags."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


# ---------- Numbers ----------

def format_int(n: Optional[int]) -> str:
    """1234567 -> '1,234,567'."""
    if n is None:
        return "—"
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def format_compact(n: Optional[int | float]) -> str:
    """1234567 -> '1.2M'; 12345 -> '12.3K'."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    if n < 1000:
        # Show ints without decimals
        if n == int(n):
            return str(int(n))
        return f"{n:.1f}"
    if n < 1_000_000:
        return f"{n / 1_000:.1f}K"
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n < 1_000_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    return f"{n / 1_000_000_000_000:.1f}T"


# ---------- File sizes ----------

def format_bytes(num_bytes: Optional[int | float]) -> str:
    """Pretty-print a byte count."""
    if num_bytes is None or num_bytes == 0:
        return "—"
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return str(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(size) < 1024.0:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} EB"


# ---------- Dates ----------

def parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # HF uses ISO 8601 with 'Z' or '+00:00'
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def format_relative_date(s: Optional[str]) -> str:
    """'2024-04-18T08:40:39.000Z' -> '2 months ago'."""
    dt = parse_iso_date(s)
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in the future"
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def format_date(s: Optional[str]) -> str:
    """ISO date -> 'Apr 18, 2024'."""
    dt = parse_iso_date(s)
    if dt is None:
        return "—"
    return dt.strftime("%b %d, %Y")


# ---------- Tags ----------

def pretty_tag(tag: str) -> str:
    """'task_categories:text-generation' -> 'Text Generation'."""
    if ":" in tag:
        prefix, value = tag.split(":", 1)
    else:
        value = tag
    # Replace dashes/underscores with spaces
    value = value.replace("-", " ").replace("_", " ")
    # Title-case but preserve acronyms (e.g. 'qa', 'ner', 'tts')
    words = value.split()
    out = []
    for w in words:
        if len(w) <= 3 and w.isupper():
            out.append(w)
        elif len(w) <= 3 and w.lower() in {"qa", "ner", "tts", "asr", "ocr", "rlhf",
                                            "sft", "dpo", "llm", "asp"}:
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def category_label(category: str) -> str:
    return {
        "task": "Task",
        "modality": "Modality",
        "size": "Size",
        "language": "Language",
        "license": "License",
        "format": "Format",
        "library": "Library",
        "region": "Region",
        "arxiv": "ArXiv",
    }.get(category, category.capitalize())


# ---------- Description ----------

def truncate(text: Optional[str], max_chars: int = 280) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    # Try to cut on a word boundary
    cut = text[:max_chars].rfind(" ")
    if cut < max_chars * 0.7:
        cut = max_chars
    return text[:cut].rstrip() + "…"


def strip_markdown(text: Optional[str]) -> str:
    """Very lightweight Markdown stripper for preview text."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Remove links, keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------- Stats ----------

def get_dataset_stats(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a normalized stats dict from a dataset response."""
    card_data = dataset.get("cardData") or {}
    dataset_info = card_data.get("dataset_info") or {}
    splits = dataset_info.get("splits") or []
    features = dataset_info.get("features") or []
    download_size = dataset_info.get("download_size") or dataset.get("usedStorage") or 0
    dataset_size = dataset_info.get("dataset_size") or 0

    total_examples = 0
    for s in splits:
        try:
            total_examples += int(s.get("num_examples", 0))
        except (TypeError, ValueError):
            pass

    return {
        "downloads": dataset.get("downloads", 0),
        "likes": dataset.get("likes", 0),
        "trendingScore": dataset.get("trendingScore", 0),
        "download_size": download_size,
        "dataset_size": dataset_size,
        "total_examples": total_examples,
        "splits": splits,
        "features": features,
        "configs": card_data.get("configs") or [],
    }
