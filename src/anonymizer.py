"""Core anonymization logic shared across file handlers."""

from __future__ import annotations

import re
from typing import Protocol

from presidio_analyzer import AnalyzerEngine


class ReplacementProvider(Protocol):
    """Protocol describing callables that generate PII replacement mappings."""

    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        """Return a dictionary mapping original PII to anonymized replacements."""


class PresidioAnonymizer:
    """Presidio-based anonymizer for PII detection with generic replacements."""

    def __init__(self, entity_types: list[str] | None = None) -> None:
        self.analyzer = AnalyzerEngine()
        # Entity types to detect (None means detect all)
        self.entity_types = entity_types

    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        """Generate PII replacement mappings for the given text.

        Args:
            text: The text to anonymize
            context: Optional context about the source (ignored, kept for compatibility)

        Returns:
            Dictionary mapping original PII to anonymized replacements
        """
        if not text or not text.strip():
            return {}

        # Analyze text to find PII
        analyzer_results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.entity_types,  # Filter by selected entity types
        )

        if not analyzer_results:
            return {}

        # Build replacement mappings using Presidio's generic format
        replacements = {}
        for result in analyzer_results:
            original_text = text[result.start : result.end]
            # Use Presidio's generic replacement format: <ENTITY_TYPE>
            replacement_text = f"<{result.entity_type}>"
            replacements[original_text] = replacement_text

        return replacements


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Apply replacement mappings to text, preserving structure and formatting.

    Replacements are applied in order of longest key first to avoid partial replacements.
    """
    if not replacements or not text:
        return text

    # Sort by length (longest first) to avoid partial replacements
    sorted_items = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)

    result = text

    for original, replacement in sorted_items:
        if original in result:
            # Use regex with word boundaries for more accurate replacement
            # Escape special regex characters in the original string
            pattern = re.escape(original)
            result = re.sub(pattern, replacement, result)

    return result


def build_replacement_provider(
    entity_types: list[str] | None = None,
) -> ReplacementProvider:
    """Return a callable that generates replacement mappings using Presidio.

    Args:
        entity_types: List of entity types to detect (e.g., ["PERSON", "EMAIL_ADDRESS"]).
                     If None, all entity types will be detected.
    """
    return PresidioAnonymizer(entity_types=entity_types)
