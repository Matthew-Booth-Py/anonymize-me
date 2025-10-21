"""PDF anonymization utilities."""

from __future__ import annotations

import io
import re

import fitz  # PyMuPDF

from .types import AnonymizedAttachment
from ..anonymizer import TextProvider


class PDFProcessor:
    """Anonymize PDF files by finding and replacing text while preserving structure."""

    def __init__(self, anonymize: TextProvider) -> None:
        self._anonymize = anonymize

    def anonymize(self, filename: str, payload: bytes) -> AnonymizedAttachment:
        # Open the PDF from bytes
        doc = fitz.open(stream=payload, filetype="pdf")

        try:
            # Process each page independently to maintain structure
            for page_num in range(len(doc)):
                page = doc[page_num]
                self._anonymize_page(page, page_num)

            # Save with optimization to maintain structure
            anonymized_content = doc.tobytes(
                garbage=4,  # Maximum garbage collection
                deflate=True,  # Compress
                clean=True,  # Clean unused objects
            )

            return AnonymizedAttachment(
                filename=filename,
                content=anonymized_content,
                maintype="application",
                subtype="pdf",
            )
        finally:
            doc.close()

    def _anonymize_page(self, page: fitz.Page, page_num: int) -> None:
        """Anonymize a single page by extracting and replacing text blocks."""
        # Extract text with detailed position information
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        
        # Collect all text blocks for anonymization
        text_blocks_info = []
        
        for block_idx, block in enumerate(blocks):
            if block.get("type") == 0:  # Text block
                # Extract text from this block
                block_text_parts = []
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                    if line_text:
                        block_text_parts.append(line_text)
                
                block_text = "\n".join(block_text_parts)
                if block_text.strip():
                    text_blocks_info.append({
                        "bbox": fitz.Rect(block["bbox"]),
                        "original_text": block_text,
                        "block": block,
                    })
        
        # Anonymize each text block
        for info in text_blocks_info:
            original_text = info["original_text"]
            bbox = info["bbox"]
            
            # Anonymize this text block
            anonymized_text = self._anonymize(
                original_text, 
                context=f"PDF page {page_num + 1}"
            )
            
            # Only process if text changed
            if anonymized_text != original_text:
                # Find individual word-level differences for precise replacement
                self._replace_text_in_area(page, bbox, original_text, anonymized_text)

    def _replace_text_in_area(
        self, 
        page: fitz.Page, 
        area_bbox: fitz.Rect, 
        original_text: str, 
        anonymized_text: str
    ) -> None:
        """Replace text within a specific area with high precision."""
        # Find word-level differences
        original_words = original_text.split()
        anonymized_words = anonymized_text.split()
        
        # Build list of replacement pairs
        replacements = []
        
        # Use a simple diff approach - find sequences that differ
        i = 0
        j = 0
        while i < len(original_words) and j < len(anonymized_words):
            if original_words[i] == anonymized_words[j]:
                i += 1
                j += 1
            else:
                # Collect differing segment
                orig_segment = []
                anon_segment = []
                
                # Look for next matching word
                match_found = False
                for look_ahead in range(1, min(10, len(original_words) - i, len(anonymized_words) - j)):
                    if original_words[i + look_ahead:i + look_ahead + 1] == anonymized_words[j + look_ahead:j + look_ahead + 1]:
                        orig_segment = original_words[i:i + look_ahead]
                        anon_segment = anonymized_words[j:j + look_ahead]
                        i += look_ahead
                        j += look_ahead
                        match_found = True
                        break
                
                if not match_found:
                    # Take single word if no match found
                    if i < len(original_words):
                        orig_segment = [original_words[i]]
                        i += 1
                    if j < len(anonymized_words):
                        anon_segment = [anonymized_words[j]]
                        j += 1
                
                if orig_segment and anon_segment:
                    orig_phrase = " ".join(orig_segment)
                    anon_phrase = " ".join(anon_segment)
                    if orig_phrase != anon_phrase:
                        replacements.append((orig_phrase, anon_phrase))
        
        # Apply replacements using redaction with careful positioning
        for original_phrase, anonymized_phrase in replacements:
            # Search for this phrase only within the specified area
            text_instances = page.search_for(original_phrase, clip=area_bbox)
            
            for inst in text_instances:
                # Use redaction to replace text
                # Get font information from the area to maintain consistency
                page.add_redact_annot(
                    inst, 
                    text=anonymized_phrase,
                    fontname="helv",  # Use Helvetica for consistency
                    fontsize=0,  # Auto-size to fit
                    fill=(1, 1, 1),  # White background
                    text_color=(0, 0, 0),  # Black text
                    align=fitz.TEXT_ALIGN_LEFT,
                )
        
        # Apply redactions only once per page (called externally)
        if replacements:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
