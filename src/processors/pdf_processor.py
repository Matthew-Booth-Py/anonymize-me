"""PDF anonymization utilities."""

from __future__ import annotations

import uuid

import fitz  # PyMuPDF

from .types import AnonymizedAttachment
from ..anonymizer import ReplacementProvider


class PDFProcessor:
    """Anonymize PDF files using Presidio while preserving ALL metadata."""

    def __init__(self, replacement_provider: ReplacementProvider) -> None:
        self._replacement_provider = replacement_provider

    def anonymize(self, filename: str, payload: bytes) -> AnonymizedAttachment:
        """Anonymize PDF content while retaining ALL metadata and structure."""
        # Open the PDF from bytes
        doc = fitz.open(stream=payload, filetype="pdf")
        
        # Extract all text from the PDF for Presidio analysis
        full_text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text()
        
        # Use Presidio to generate replacements
        replacements = self._replacement_provider(full_text, context="PDF attachment")

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

            # Generate random filename
            random_filename = f"{uuid.uuid4().hex[:12]}.pdf"

            return AnonymizedAttachment(
                filename=random_filename,
                content=anonymized_content,
                maintype="application",
                subtype="pdf",
            )
        finally:
            doc.close()

    def _apply_replacements_to_page(
        self, page: fitz.Page, replacements: dict[str, str]
    ) -> None:
        """Apply all replacements to a single page using Helvetica font."""
        if not replacements:
            return

        # Sort replacements by length (longest first) to avoid partial replacements
        sorted_replacements = sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True
        )

        # Track replacements to make
        replacements_to_apply = []

        # For each replacement, find all instances in the text blocks
        for original, replacement in sorted_replacements:
            if not original or original == replacement:
                continue

            # Search for text instances and get their exact positions
            text_instances = page.search_for(original)

            if not text_instances:
                continue

            # For each instance, store the rect for replacement
            for idx, rect in enumerate(text_instances):
                replacements_to_apply.append(
                    {
                        "rect": rect,
                        "original": original,
                        "replacement": replacement,
                    }
                )

        if not replacements_to_apply:
            return

        # Add all redaction annotations with replacement text
        for item in replacements_to_apply:
            rect = item["rect"]
            replacement = item["replacement"]
            original = item["original"]

            # Use Helvetica font and calculate size based on rect height
            fontname = "helv"
            fontsize = rect.height * 0.7

            # Calculate width ratio to adjust font size if replacement is longer
            if len(original) > 0:
                width_ratio = len(replacement) / len(original)
                if width_ratio > 1.2:  # Replacement is significantly longer
                    fontsize = fontsize / width_ratio

            # Add redaction annotation with replacement text
            page.add_redact_annot(
                rect,
                text=replacement,
                fontname=fontname,
                fontsize=fontsize,
                fill=(1, 1, 1),  # White background
                text_color=(0, 0, 0),  # Black text
                align=fitz.TEXT_ALIGN_LEFT,
            )

        # Apply all redactions at once
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
