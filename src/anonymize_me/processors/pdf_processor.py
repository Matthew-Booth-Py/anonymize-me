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

        # Get all text on page
        page_text = page.get_text()
        print(f"DEBUG PDF: Original page text preview: {page_text[:200]}...")

        # Apply text replacements to the entire page text
        modified_text = apply_replacements(page_text, replacements)
        
        if modified_text == page_text:
            print(f"DEBUG PDF: No changes needed for this page")
            return
        
        print(f"DEBUG PDF: Text was modified, rewriting page...")
        
        # Get detailed text with positions
        blocks = page.get_text("dict")["blocks"]
        
        # Collect all replacements to make (don't modify yet)
        text_replacements = []
        
        # Process each text block to find what needs replacing
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        original_text = span.get("text", "")
                        if not original_text:
                            continue
                        
                        # Apply replacements to this span's text
                        new_text = apply_replacements(original_text, replacements)
                        
                        if new_text != original_text:
                            # Get the bounding box for this span
                            bbox = fitz.Rect(span["bbox"])
                            fontsize = span.get("size", 11)
                            fontname = span.get("font", "helv")
                            
                            # Map PDF font names to PyMuPDF font names
                            if "bold" in fontname.lower():
                                fontname = "helb"
                            elif "italic" in fontname.lower():
                                fontname = "heli"
                            else:
                                fontname = "helv"
                            
                            text_replacements.append({
                                "bbox": bbox,
                                "original": original_text,
                                "new": new_text,
                                "fontsize": fontsize,
                                "fontname": fontname
                            })
        
        if not text_replacements:
            print(f"DEBUG PDF: No span-level replacements needed")
            return
        
        print(f"DEBUG PDF: Found {len(text_replacements)} spans to replace")
        
        # Step 1: Add all redaction annotations
        for item in text_replacements:
            page.add_redact_annot(item["bbox"], fill=(1, 1, 1))
        
        # Step 2: Apply all redactions at once
        page.apply_redactions(images=0)
        print(f"DEBUG PDF: Applied all redactions")
        
        # Step 3: Insert all replacement text
        for item in text_replacements:
            result = page.insert_textbox(
                item["bbox"],
                item["new"],
                fontsize=item["fontsize"],
                fontname=item["fontname"],
                color=(0, 0, 0),
                align=0,  # left align
            )
            if result < 0:
                print(f"DEBUG PDF: Failed to insert '{item['new']}' (result={result})")
            else:
                print(f"DEBUG PDF: Inserted '{item['new']}' -> '{item['original']}'")
        
        print(f"DEBUG PDF: Completed {len(text_replacements)} span replacements")
        
        # Verify
        final_text = page.get_text()
        print(f"DEBUG PDF: Final page text: {final_text[:200]}...")
