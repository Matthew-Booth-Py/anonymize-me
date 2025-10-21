"""Processor for plain text payloads."""

from __future__ import annotations

from .types import AnonymizedAttachment
from ..anonymizer import apply_replacements


def anonymize_text_payload(
    name: str, 
    content: str, 
    replacements: dict[str, str]
) -> AnonymizedAttachment:
    """Return an anonymized text attachment preserving the input filename."""
    sanitized = apply_replacements(content, replacements)
    anonymized_filename = apply_replacements(name, replacements)
    return AnonymizedAttachment(
        filename=anonymized_filename, 
        content=sanitized.encode("utf-8"), 
        maintype="text", 
        subtype="plain"
    )
