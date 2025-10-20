"""Utilities for anonymizing EML messages and their attachments."""

from __future__ import annotations

import email
from email import policy
from email.message import EmailMessage, Message

from .anonymizer import TextProvider
from .processors.docx_processor import DocxProcessor
from .processors.pdf_processor import PDFProcessor
from .processors.text_processor import anonymize_text_payload
from .processors.types import AnonymizedAttachment


class EmailAnonymizer:
    """Anonymize an ``.eml`` message including supported attachments."""

    def __init__(self, text_anonymizer: TextProvider) -> None:
        self._text_anonymizer = text_anonymizer
        self._pdf_processor = PDFProcessor(text_anonymizer)
        self._docx_processor = DocxProcessor(text_anonymizer)

    def anonymize(self, raw_eml: bytes) -> bytes:
        original = email.message_from_bytes(raw_eml, policy=policy.default)
        anonymized = self._clone_structure(original)
        return anonymized.as_bytes()

    def _clone_structure(self, message: Message) -> EmailMessage:
        clone = EmailMessage()
        for header, value in message.items():
            clone[header] = self._text_anonymizer(value, context=f"Email header: {header}") if value else value

        if message.is_multipart():
            clone.make_mixed()
            for part in message.iter_parts():
                processed_part = self._process_part(part)
                if isinstance(processed_part, EmailMessage):
                    clone.attach(processed_part)
                else:
                    attachment = processed_part
                    clone.add_attachment(
                        attachment.content,
                        maintype=attachment.maintype,
                        subtype=attachment.subtype,
                        filename=attachment.filename,
                    )
        else:
            payload = message.get_content()
            if message.get_content_subtype() == "html":
                sanitized = self._text_anonymizer(payload, context="HTML body")
                clone.add_alternative(sanitized, subtype="html")
            else:
                sanitized = self._text_anonymizer(payload, context="Text body")
                clone.set_content(sanitized, subtype=message.get_content_subtype())

        return clone

    def _process_part(self, part: Message) -> EmailMessage | AnonymizedAttachment:
        if part.is_multipart():
            return self._clone_structure(part)

        filename = part.get_filename()
        maintype = part.get_content_maintype()
        subtype = part.get_content_subtype()

        if maintype == "text":
            payload = part.get_content()
            context = f"text/{subtype} attachment" if subtype else "text attachment"
            sanitized = self._text_anonymizer(payload, context=context)
            message = EmailMessage()
            message.set_content(sanitized, subtype=subtype)
            if filename:
                message.add_header("Content-Disposition", "attachment", filename=filename)
            return message

        if filename:
            payload_bytes = part.get_payload(decode=True) or b""
            lowered = filename.lower()
            if lowered.endswith(".pdf"):
                return self._pdf_processor.anonymize(filename, payload_bytes)
            if lowered.endswith(".docx") or lowered.endswith(".doc"):
                return self._docx_processor.anonymize(filename, payload_bytes)

        payload_text = part.get_content()
        return anonymize_text_payload(filename or "attachment.txt", payload_text, self._text_anonymizer)


def anonymize_eml(raw_eml: bytes, text_anonymizer: TextProvider) -> bytes:
    """Convenience wrapper around :class:`EmailAnonymizer`."""

    return EmailAnonymizer(text_anonymizer).anonymize(raw_eml)
