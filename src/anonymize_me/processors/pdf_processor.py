"""PDF anonymization utilities."""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .types import AnonymizedAttachment
from ..anonymizer import TextProvider


class PDFProcessor:
    """Anonymize PDF files on a page-by-page basis."""

    def __init__(self, anonymize: TextProvider) -> None:
        self._anonymize = anonymize

    def anonymize(self, filename: str, payload: bytes) -> AnonymizedAttachment:
        reader = PdfReader(io.BytesIO(payload))
        writer = PdfWriter()

        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            sanitized_text = self._anonymize(page_text, context=f"PDF page {index}")

            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            buffer = io.BytesIO()
            canv = canvas.Canvas(buffer, pagesize=(width, height))
            text_obj = canv.beginText(36, height - 54)
            for line in sanitized_text.splitlines() or [""]:
                text_obj.textLine(line)
            canv.drawText(text_obj)
            canv.showPage()
            canv.save()
            buffer.seek(0)

            sanitized_page = PdfReader(buffer).pages[0]
            writer.add_page(sanitized_page)

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        return AnonymizedAttachment(
            filename=filename,
            content=output_buffer.getvalue(),
            maintype="application",
            subtype="pdf",
        )
