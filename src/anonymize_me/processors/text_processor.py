"""Processor for plain text payloads."""

from __future__ import annotations

from .types import AnonymizedAttachment
from ..anonymizer import TextProvider


def anonymize_text_payload(name: str, content: str, anonymize: TextProvider) -> AnonymizedAttachment:
    """Return an anonymized text attachment preserving the input filename."""
    sanitized = anonymize(content)
    return AnonymizedAttachment(filename=name, content=sanitized.encode("utf-8"), maintype="text", subtype="plain")
