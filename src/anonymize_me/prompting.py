"""Utilities for loading anonymization prompts."""

from __future__ import annotations

from pathlib import Path

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "prompt_template.txt"


def load_prompt_template() -> str:
    """Return the anonymization prompt template shipped with the project."""
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
