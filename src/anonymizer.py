"""Core anonymization logic shared across file handlers."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Protocol

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


class ReplacementProvider(Protocol):
    """Protocol describing callables that generate PII replacement mappings."""

    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        """Return a dictionary mapping original PII to anonymized replacements."""


class PresidioAnonymizer:
    """Presidio-based anonymizer for PII detection and replacement."""

    def __init__(self, entity_types: list[str] | None = None) -> None:
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        # Track entity counts for consistent naming (Person A, Person B, etc.)
        self.entity_counters = defaultdict(int)
        self.entity_cache = {}  # Cache original -> replacement mappings
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

        # Build replacement mappings with consistent, readable names
        replacements = {}

        for result in analyzer_results:
            original_text = text[result.start : result.end]

            # Skip if we already have a replacement for this text
            if original_text in self.entity_cache:
                replacements[original_text] = self.entity_cache[original_text]
                continue

            # Generate replacement based on entity type
            replacement = self._generate_replacement(result.entity_type, original_text)

            # Cache the mapping
            self.entity_cache[original_text] = replacement
            replacements[original_text] = replacement

        return replacements

    def _generate_replacement(self, entity_type: str, original: str) -> str:
        """Generate a readable replacement for a PII entity."""
        # Increment counter for this entity type
        self.entity_counters[entity_type] += 1
        count = self.entity_counters[entity_type]

        # Generate replacement based on type
        if entity_type == "PERSON":
            return f"Person {chr(64 + count)}"  # Person A, Person B, etc.
        elif entity_type == "EMAIL_ADDRESS":
            return f"person{chr(96 + count)}@example.com"  # persona@, personb@, etc.
        elif entity_type == "PHONE_NUMBER":
            return f"555-000-{count:04d}"
        elif entity_type == "LOCATION":
            return f"City {chr(64 + count)}"
        elif entity_type in ("US_SSN", "UK_NHS"):
            return "XXX-XX-XXXX"
        elif entity_type == "CREDIT_CARD":
            return "XXXX-XXXX-XXXX-XXXX"
        elif entity_type == "IBAN_CODE":
            return "XX00 0000 0000 0000"
        elif entity_type == "IP_ADDRESS":
            return "0.0.0.0"
        elif entity_type == "DATE_TIME":
            return "XXXX-XX-XX"
        elif entity_type == "NRP":  # Nationality/Religion/Political group
            return f"Group {chr(64 + count)}"
        elif entity_type == "US_DRIVER_LICENSE":
            return "XXXXXXXX"
        elif entity_type == "CRYPTO":
            return "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # Generic crypto address
        elif entity_type == "MEDICAL_LICENSE":
            return "MED-XXXXXX"
        elif entity_type == "URL":
            return "https://example.com"
        elif entity_type == "US_BANK_NUMBER":
            return "XXXXXXXXXX"
        elif entity_type == "US_ITIN":
            return "9XX-XX-XXXX"
        elif entity_type == "US_PASSPORT":
            return "XXXXXXXXX"
        else:
            # Generic replacement for unknown types
            return f"[REDACTED-{entity_type}]"


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
