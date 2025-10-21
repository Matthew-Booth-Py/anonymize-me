"""Email anonymization processor with attachment handling."""

from __future__ import annotations

import email
from email import policy
from email.message import EmailMessage, Message

from .docx_processor import DocxProcessor
from .pdf_processor import PDFProcessor
from .text_processor import anonymize_text_payload
from .types import AnonymizedAttachment
from ..anonymizer import ReplacementProvider, apply_replacements


class EmailProcessor:
    """
    Process and anonymize EML files using Presidio:
    - Email body/headers are analyzed and anonymized
    - Each attachment (PDF, DOCX) analyzes its own content with Presidio
    - The same ReplacementProvider instance ensures consistent replacements across all parts
    """

    def __init__(self, replacement_provider: ReplacementProvider) -> None:
        self._replacement_provider = replacement_provider
        self._pdf_processor = PDFProcessor(replacement_provider)
        self._docx_processor = DocxProcessor(replacement_provider)

    def anonymize(self, raw_eml: bytes) -> bytes:
        """Anonymize an email and all its attachments."""
        # Parse the original email
        original = email.message_from_bytes(raw_eml, policy=policy.default)

        # Step 1: Extract all text content from email for replacement mapping
        all_text = self._extract_all_text(original)

        # Step 2: Generate replacement mappings using LLM
        replacements = self._replacement_provider(
            all_text, context="Complete email with all attachments"
        )

        # Step 3: Apply replacements to create anonymized email
        anonymized = self._clone_and_anonymize(original, replacements)

        return anonymized.as_bytes()

    def _extract_all_text(self, message: Message) -> str:
        """Extract all text content from email including headers and attachments."""
        text_parts = []

        # Extract headers
        for header, value in message.items():
            if value:
                text_parts.append(f"{header}: {value}")

        # Extract body and attachments
        if message.is_multipart():
            for part in message.iter_parts():
                text_parts.append(self._extract_part_text(part))
        else:
            # Simple message with body only
            try:
                payload = message.get_content()
                if isinstance(payload, str):
                    text_parts.append(payload)
            except Exception:
                pass

        return "\n\n".join(filter(None, text_parts))

    def _extract_part_text(self, part: Message) -> str:
        """Extract text from a message part."""
        if part.is_multipart():
            # Recursively extract from multipart
            parts = []
            for subpart in part.iter_parts():
                parts.append(self._extract_part_text(subpart))
            return "\n".join(filter(None, parts))

        maintype = part.get_content_maintype()

        # Extract text content
        if maintype == "text":
            try:
                return part.get_content()
            except Exception:
                return ""

        # For binary attachments, try to extract text if possible
        filename = part.get_filename()
        if filename:
            try:
                payload_bytes = part.get_payload(decode=True) or b""
                lowered = filename.lower()

                # Extract text from PDF
                if lowered.endswith(".pdf"):
                    return self._extract_pdf_text(payload_bytes)

                # For other types, just note the filename
                return f"Attachment: {filename}"
            except Exception:
                return f"Attachment: {filename}"

        return ""

    def _extract_pdf_text(self, payload: bytes) -> str:
        """Extract text from PDF for replacement mapping generation."""
        try:
            import fitz

            doc = fitz.open(stream=payload, filetype="pdf")
            try:
                text_parts = []
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text_parts.append(page.get_text())
                return "\n".join(text_parts)
            finally:
                doc.close()
        except Exception:
            return ""

    def _clone_and_anonymize(
        self, message: Message, replacements: dict[str, str]
    ) -> EmailMessage:
        """Clone message structure and apply replacements."""
        clone = EmailMessage()

        # Copy and anonymize headers (skip Content-Type as it's set by make_mixed/set_content)
        for header, value in message.items():
            if header.lower() == "content-type":
                continue
            anonymized_value = (
                apply_replacements(value, replacements) if value else value
            )
            clone[header] = anonymized_value

        # Process content
        if message.is_multipart():
            subtype = message.get_content_subtype()
            if subtype == "alternative":
                clone.make_alternative()
            elif subtype == "related":
                clone.make_related()
            else:
                clone.make_mixed()

            if message.preamble:
                clone.preamble = apply_replacements(message.preamble, replacements)
            if message.epilogue:
                clone.epilogue = apply_replacements(message.epilogue, replacements)
            for part in message.iter_parts():
                processed_part = self._process_part(part, replacements)
                if isinstance(processed_part, EmailMessage):
                    clone.attach(processed_part)
                else:
                    # Attach as anonymized attachment
                    attachment = processed_part
                    clone.add_attachment(
                        attachment.content,
                        maintype=attachment.maintype,
                        subtype=attachment.subtype,
                        filename=attachment.filename,
                    )
        else:
            # Simple message body
            try:
                payload = message.get_content()
                if isinstance(payload, str):
                    sanitized = apply_replacements(payload, replacements)
                    if message.get_content_subtype() == "html":
                        clone.add_alternative(sanitized, subtype="html")
                    else:
                        clone.set_content(
                            sanitized, subtype=message.get_content_subtype()
                        )
            except Exception:
                # If content extraction fails, skip
                pass

        return clone

    def _process_part(
        self, part: Message, replacements: dict[str, str]
    ) -> EmailMessage | AnonymizedAttachment:
        """Process a message part (body or attachment) with replacements."""
        if part.is_multipart():
            return self._clone_and_anonymize(part, replacements)

        filename = part.get_filename()
        maintype = part.get_content_maintype()
        subtype = part.get_content_subtype()

        # Handle text parts (only if they have a filename - otherwise they're the body)
        if maintype == "text" and filename:
            try:
                import uuid
                from pathlib import Path

                payload = part.get_content()
                sanitized = apply_replacements(payload, replacements)
                charset = part.get_content_charset() or "utf-8"

                # Generate random filename, preserve extension
                ext = Path(filename).suffix or ".txt"
                random_filename = f"{uuid.uuid4().hex[:12]}{ext}"

                message = EmailMessage()
                message.set_content(sanitized, subtype=subtype, charset=charset)
                disposition = part.get_content_disposition() or "attachment"
                message.add_header(
                    "Content-Disposition", disposition, filename=random_filename
                )
                if part.get("Content-ID"):
                    message["Content-ID"] = part["Content-ID"]
                return message
            except Exception:
                # Fall through to default handling
                pass

        # If it's text without a filename, it's the message body - return it as EmailMessage
        if maintype == "text":
            try:
                payload = part.get_content()
                sanitized = apply_replacements(payload, replacements)
                charset = part.get_content_charset() or "utf-8"
                message = EmailMessage()
                message.set_content(sanitized, subtype=subtype, charset=charset)
                for header in ("Content-ID", "Content-Location"):
                    if part.get(header):
                        message[header] = part[header]
                disposition = part.get_content_disposition()
                if disposition:
                    message["Content-Disposition"] = disposition
                return message
            except Exception:
                pass

        # Handle binary attachments (PDF, DOCX, etc.)
        if filename:
            payload_bytes = part.get_payload(decode=True) or b""
            lowered = filename.lower()

            if lowered.endswith(".pdf"):
                return self._pdf_processor.anonymize(filename, payload_bytes)

            if lowered.endswith(".docx") or lowered.endswith(".doc"):
                return self._docx_processor.anonymize(filename, payload_bytes)

        # Default: treat as text if possible
        try:
            payload_text = part.get_content()
            return anonymize_text_payload(
                filename or "attachment.txt", payload_text, replacements
            )
        except Exception:
            # If all else fails, return as-is with random filename
            import uuid
            from pathlib import Path

            ext = Path(filename).suffix if filename else ".bin"
            random_filename = f"{uuid.uuid4().hex[:12]}{ext}"

            return AnonymizedAttachment(
                filename=random_filename,
                content=part.get_payload(decode=True) or b"",
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
            )


def anonymize_eml(raw_eml: bytes, replacement_provider: ReplacementProvider) -> bytes:
    """Convenience wrapper around EmailProcessor."""
    processor = EmailProcessor(replacement_provider)
    return processor.anonymize(raw_eml)
