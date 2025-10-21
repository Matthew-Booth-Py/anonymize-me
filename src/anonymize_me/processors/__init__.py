"""Attachment processors for the Anonymize Me application."""

from .docx_processor import DocxProcessor
from .email_processor import EmailProcessor, anonymize_eml
from .pdf_processor import PDFProcessor
from .text_processor import anonymize_text_payload
from .types import AnonymizedAttachment

__all__ = [
    "DocxProcessor",
    "EmailProcessor", 
    "PDFProcessor",
    "anonymize_eml",
    "anonymize_text_payload",
    "AnonymizedAttachment",
]
