"""Shared dataclasses for processed attachments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AnonymizedAttachment:
    """Represents an anonymized attachment ready to embed into an email."""

    filename: str
    content: bytes
    maintype: str
    subtype: str
