"""PDF anonymization utilities."""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from .types import AnonymizedAttachment
from ..anonymizer import apply_replacements


class PDFProcessor:
    """Anonymize PDF files using replacement mappings while preserving ALL metadata."""

    def anonymize(
        self, 
        filename: str, 
        payload: bytes, 
        replacements: dict[str, str]
    ) -> AnonymizedAttachment:
        """Anonymize PDF content while retaining ALL metadata and structure."""
        # Open the PDF from bytes
        doc = fitz.open(stream=payload, filetype="pdf")

        try:
            # Process each page to apply replacements
            for page_num in range(len(doc)):
                page = doc[page_num]
                self._apply_replacements_to_page(page, replacements)

            # Save with ALL metadata preserved - use incremental save settings
            anonymized_content = doc.tobytes(
                garbage=0,  # Don't remove anything
                deflate=True,  # Compress streams
                clean=False,  # Don't clean - preserves metadata
                pretty=False,  # Compact output
                ascii=False,  # Keep binary
                linear=False,  # Don't linearize
                no_new_id=True,  # Keep original document ID
            )

            # Anonymize filename
            anonymized_filename = apply_replacements(filename, replacements)

            return AnonymizedAttachment(
                filename=anonymized_filename,
                content=anonymized_content,
                maintype="application",
                subtype="pdf",
            )
        finally:
            doc.close()

    def _apply_replacements_to_page(
        self, 
        page: fitz.Page, 
        replacements: dict[str, str]
    ) -> None:
        """Apply all replacements to a single page by rewriting text blocks."""
        if not replacements:
            return

        # Search for every replacement on the page. Using ``search_for`` ensures
        # we catch matches that are split across multiple spans or text blocks
        # (a common layout for PDF generators).
        search_plan: list[tuple[fitz.Rect, str, str]] = []

        sorted_replacements = sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True
        )

        for original, replacement in sorted_replacements:
            if not original or original == replacement:
                continue

            # ``search_for`` returns the bounding rectangles for each match. We
            # normalise them to ``fitz.Rect`` instances for later processing.
            matches = page.search_for(original)
            if not matches:
                continue

            for match in matches:
                search_plan.append((fitz.Rect(match), original, replacement))

        if not search_plan:
            print("DEBUG PDF: No matches found for replacements on this page")
            return

        print(f"DEBUG PDF: Preparing {len(search_plan)} redactions via search")

        # Add redaction annotations for every match before applying them. This
        # prevents us from mutating the page while still iterating over results.
        for bbox, *_ in search_plan:
            page.add_redact_annot(bbox, fill=(1, 1, 1))

        page.apply_redactions(images=0)
        print("DEBUG PDF: Applied redactions from search plan")

        # Reinsert the anonymised text in the cleared rectangles. Use the
        # rectangle height to estimate a sensible font size so the replacement
        # text fits within the original bounds.
        for bbox, original, replacement in search_plan:
            estimated_fontsize = max(bbox.height * 0.8, 6)
            result = page.insert_textbox(
                bbox,
                replacement,
                fontsize=estimated_fontsize,
                fontname="helv",
                color=(0, 0, 0),
                align=0,
            )
            if result < 0:
                print(
                    f"DEBUG PDF: Fallback insert for '{replacement}' (result={result})"
                )
                page.insert_text(
                    bbox.tl,
                    replacement,
                    fontsize=estimated_fontsize,
                    fontname="helv",
                    color=(0, 0, 0),
                )
            else:
                print(
                    f"DEBUG PDF: Inserted replacement for '{original}' -> '{replacement}'"
                )

        final_text = page.get_text()
        print(f"DEBUG PDF: Final page text: {final_text[:200]}...")
