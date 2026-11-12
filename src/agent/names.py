"""Normalize agent / tool names for catalog keys and tool schemas."""

from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"

    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"

    return cleaned.lower()
