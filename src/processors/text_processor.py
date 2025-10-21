"""Processor for plain text payloads."""

from __future__ import annotations

import uuid
from pathlib import Path

from .types import AnonymizedAttachment
from ..anonymizer import apply_replacements


def anonymize_text_payload(
    name: str, 
    content: str, 
    replacements: dict[str, str]
) -> AnonymizedAttachment:
    """Return an anonymized text attachment with a random filename."""
    sanitized = apply_replacements(content, replacements)
    
    # Generate random filename, preserve extension if available
    ext = Path(name).suffix or ".txt"
    random_filename = f"{uuid.uuid4().hex[:12]}{ext}"
    
    return AnonymizedAttachment(
        filename=random_filename, 
        content=sanitized.encode("utf-8"), 
        maintype="text", 
        subtype="plain"
    )
