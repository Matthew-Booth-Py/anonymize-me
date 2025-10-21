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

    def _rectangles_overlap(self, rect1: fitz.Rect, rect2: fitz.Rect, threshold: float = 0.5) -> bool:
        """Check if two rectangles overlap significantly.
        
        Args:
            rect1: First rectangle
            rect2: Second rectangle
            threshold: Overlap threshold (0.0 to 1.0). If the overlap area is more than
                      this fraction of the smaller rectangle, consider them overlapping.
        
        Returns:
            True if rectangles overlap significantly
        """
        # Get intersection rectangle
        intersection = rect1 & rect2  # PyMuPDF's intersection operator
        
        if intersection.is_empty:
            return False
        
        # Calculate areas manually (width * height)
        intersection_area = intersection.width * intersection.height
        rect1_area = rect1.width * rect1.height
        rect2_area = rect2.width * rect2.height
        
        if rect1_area == 0 or rect2_area == 0:
            return False
        
        # Calculate overlap percentage relative to the smaller rectangle
        smaller_area = min(rect1_area, rect2_area)
        overlap_ratio = intersection_area / smaller_area
        
        return overlap_ratio > threshold

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
        processed_rects = []  # Track rectangles we've already processed

        # For each replacement, find all instances in the text blocks
        for original, replacement in sorted_replacements:
            if not original or original == replacement:
                continue

            # Search for text instances and get their exact positions
            text_instances = page.search_for(original)

            if not text_instances:
                continue

            # For each instance, check if it overlaps with already processed rectangles
            for rect in text_instances:
                # Check if this rectangle overlaps significantly with any already processed
                is_duplicate = False
                for processed in processed_rects:
                    if self._rectangles_overlap(rect, processed):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    replacements_to_apply.append(
                        {
                            "rect": rect,
                            "original": original,
                            "replacement": replacement,
                        }
                    )
                    processed_rects.append(rect)

        if not replacements_to_apply:
            return

        # First pass: Add redaction annotations to remove original text
        for item in replacements_to_apply:
            rect = item["rect"]
            # Add redaction with white fill to completely cover original text
            page.add_redact_annot(
                rect,
                fill=(1, 1, 1),  # White background to cover original
            )

        # Apply all redactions to remove original text
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # Second pass: Add replacement text on the clean white rectangles
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

            # Insert text at the rectangle position
            # Adjust y position to align text properly (baseline)
            text_point = fitz.Point(rect.x0, rect.y0 + rect.height * 0.75)
            
            page.insert_text(
                text_point,
                replacement,
                fontname=fontname,
                fontsize=fontsize,
                color=(0, 0, 0),  # Black text
            )
