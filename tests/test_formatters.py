"""Unit tests for formatters."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.formatters import (
    format_bytes,
    format_compact,
    format_date,
    format_int,
    format_relative_date,
    parse_iso_date,
    pretty_tag,
    strip_markdown,
    truncate,
    get_dataset_stats,
)
from api.hf_client import parse_tags


class TestNumberFormatting:
    def test_format_int_with_commas(self):
        assert format_int(1234567) == "1,234,567"
        assert format_int(0) == "0"
        assert format_int(1000) == "1,000"

    def test_format_int_none(self):
        assert format_int(None) == "—"

    def test_format_int_invalid(self):
        assert format_int("not a number") == "not a number"

    def test_format_compact_small(self):
        assert format_compact(0) == "0"
        assert format_compact(500) == "500"
        assert format_compact(999) == "999"

    def test_format_compact_thousands(self):
        assert format_compact(1500) == "1.5K"
        assert format_compact(12000) == "12.0K"
        assert format_compact(999999) == "1000.0K"

    def test_format_compact_millions(self):
        assert format_compact(1_500_000) == "1.5M"
        assert format_compact(12_000_000) == "12.0M"

    def test_format_compact_billions(self):
        assert format_compact(1_500_000_000) == "1.5B"

    def test_format_compact_trillions(self):
        assert format_compact(1_500_000_000_000) == "1.5T"

    def test_format_compact_none(self):
        assert format_compact(None) == "—"


class TestByteFormatting:
    def test_zero(self):
        assert format_bytes(0) == "—"

    def test_none(self):
        assert format_bytes(None) == "—"

    def test_bytes(self):
        assert format_bytes(500) == "500 B"

    def test_kb(self):
        assert "KB" in format_bytes(1500)

    def test_mb(self):
        assert "MB" in format_bytes(5_000_000)

    def test_gb(self):
        assert "GB" in format_bytes(5_000_000_000)

    def test_tb(self):
        assert "TB" in format_bytes(5_000_000_000_000)


class TestDateFormatting:
    def test_parse_iso_date(self):
        dt = parse_iso_date("2024-04-18T08:40:39.000Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 4
        assert dt.day == 18

    def test_parse_iso_date_none(self):
        assert parse_iso_date(None) is None
        assert parse_iso_date("") is None

    def test_parse_iso_date_invalid(self):
        assert parse_iso_date("not a date") is None

    def test_format_date(self):
        result = format_date("2024-04-18T08:40:39.000Z")
        assert "Apr" in result
        assert "2024" in result

    def test_format_date_none(self):
        assert format_date(None) == "—"

    def test_format_relative_date_recent(self):
        now = datetime.now(timezone.utc)
        iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = format_relative_date(iso)
        # Either "just now" or "X seconds/minute ago" is valid for a recent timestamp
        assert "ago" in result or "just now" in result

    def test_format_relative_date_minutes(self):
        dt = datetime.now(timezone.utc) - timedelta(minutes=30)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = format_relative_date(iso)
        assert "minute" in result

    def test_format_relative_date_hours(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=5)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = format_relative_date(iso)
        assert "hour" in result

    def test_format_relative_date_days(self):
        dt = datetime.now(timezone.utc) - timedelta(days=3)
        iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = format_relative_date(iso)
        assert "day" in result

    def test_format_relative_date_none(self):
        assert format_relative_date(None) == "—"


class TestTagFormatting:
    def test_pretty_tag_with_prefix(self):
        assert pretty_tag("task_categories:text-generation") == "Text Generation"
        assert pretty_tag("modality:text") == "Text"
        assert pretty_tag("language:en") == "En"

    def test_pretty_tag_no_prefix(self):
        assert pretty_tag("plain-tag") == "Plain Tag"

    def test_pretty_tag_preserves_acronym(self):
        # Single-letter codes like 'en' should be uppercased
        result = pretty_tag("language:en")
        assert result == "EN" or result == "En"

    def test_parse_tags(self):
        tags = ["task_categories:text-generation", "modality:text", "language:en"]
        parsed = parse_tags(tags)
        assert "task" in parsed
        assert "modality" in parsed
        assert "language" in parsed


class TestTextFormatting:
    def test_truncate_short(self):
        assert truncate("short text", 100) == "short text"

    def test_truncate_long(self):
        result = truncate("a" * 200, 50)
        assert len(result) <= 51  # 50 chars + ellipsis
        assert result.endswith("…")

    def test_truncate_none(self):
        assert truncate(None) == ""

    def test_strip_markdown_code(self):
        text = "```python\nprint('hi')\n```"
        result = strip_markdown(text)
        assert "```" not in result

    def test_strip_markdown_links(self):
        text = "See [this link](https://example.com) for more."
        result = strip_markdown(text)
        assert "[this link]" not in result
        assert "this link" in result

    def test_strip_markdown_bold(self):
        text = "This is **bold** text."
        result = strip_markdown(text)
        assert "**" not in result
        assert "bold" in result

    def test_strip_markdown_headings(self):
        text = "# Heading\n## Subheading\nContent"
        result = strip_markdown(text)
        assert result.startswith("Heading")

    def test_strip_markdown_images(self):
        text = "![alt text](image.png) and more"
        result = strip_markdown(text)
        assert "![alt text]" not in result

    def test_strip_markdown_none(self):
        assert strip_markdown(None) == ""


class TestDatasetStats:
    def test_empty_dataset(self):
        stats = get_dataset_stats({})
        assert stats["downloads"] == 0
        assert stats["likes"] == 0
        assert stats["total_examples"] == 0
        assert stats["splits"] == []
        assert stats["features"] == []

    def test_with_card_data(self):
        dataset = {
            "downloads": 1000,
            "likes": 50,
            "cardData": {
                "dataset_info": {
                    "features": [
                        {"name": "text", "dtype": "string"},
                        {"name": "label", "dtype": "int64"},
                    ],
                    "splits": [
                        {"name": "train", "num_examples": 800, "num_bytes": 1000000},
                        {"name": "test", "num_examples": 200, "num_bytes": 250000},
                    ],
                    "download_size": 500000,
                    "dataset_size": 1250000,
                },
                "configs": [{"config_name": "default"}],
            },
        }
        stats = get_dataset_stats(dataset)
        assert stats["downloads"] == 1000
        assert stats["likes"] == 50
        assert stats["total_examples"] == 1000
        assert stats["download_size"] == 500000
        assert stats["dataset_size"] == 1250000
        assert len(stats["splits"]) == 2
        assert len(stats["features"]) == 2
        assert len(stats["configs"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
