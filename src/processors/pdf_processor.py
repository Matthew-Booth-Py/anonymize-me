"""PDF anonymization utilities."""

from __future__ import annotations

import re
import uuid

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
        self, 
        page: fitz.Page, 
        replacements: dict[str, str]
    ) -> None:
        """Apply all replacements to a single page while preserving formatting."""
        if not replacements:
            return
        
        # Get text with detailed character-level information
        text_page = page.get_text("dict")
        blocks = text_page.get("blocks", [])
        
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
            
            # For each instance, extract formatting from the underlying text
            for idx, rect in enumerate(text_instances):
                # Find the formatting information for this text
                font_info = self._extract_font_info_at_rect(blocks, rect, original)
                
                replacements_to_apply.append({
                    'rect': rect,
                    'original': original,
                    'replacement': replacement,
                    'font_info': font_info
                })

        if not replacements_to_apply:
            return
        
        # Add all redaction annotations with replacement text
        for item in replacements_to_apply:
            rect = item['rect']
            replacement = item['replacement']
            original = item['original']
            font_info = item['font_info']
            
            if font_info:
                # Use the original font information
                fontname = font_info.get('fontname', 'helv')
                fontsize = font_info.get('fontsize', rect.height * 0.7)
                color = font_info.get('color', (0, 0, 0))
            else:
                # Fallback to calculated values
                fontname = 'helv'
                fontsize = rect.height * 0.7
                color = (0, 0, 0)
            
            # Calculate width ratio to adjust font size if needed
            if len(original) > 0:
                width_ratio = len(replacement) / len(original)
                if width_ratio > 1.2:  # Replacement is significantly longer
                    fontsize = fontsize / width_ratio
            
            # Add redaction annotation with replacement text built-in
            # This uses PyMuPDF's native capability to replace text during redaction
            page.add_redact_annot(
                rect,
                text=replacement,
                fontname=fontname,
                fontsize=fontsize,
                fill=color,
                text_color=color,
                align=fitz.TEXT_ALIGN_LEFT
            )
        
        # Apply all redactions at once
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    
    def _extract_font_info_at_rect(
        self, 
        blocks: list, 
        rect: fitz.Rect, 
        target_text: str
    ) -> dict | None:
        """Extract font information for text at a specific rectangle."""
        # Expand rect slightly to catch text that might be slightly off
        search_rect = fitz.Rect(
            rect.x0 - 2, 
            rect.y0 - 2, 
            rect.x1 + 2, 
            rect.y1 + 2
        )
        
        # Search through all blocks for text in this area
        for block in blocks:
            if block.get("type") != 0:  # Not a text block
                continue
            
            for line in block.get("lines", []):
                line_rect = fitz.Rect(line["bbox"])
                
                # Check if this line intersects with our search area
                if not line_rect.intersects(search_rect):
                    continue
                
                # Check spans (individual text segments with consistent formatting)
                for span in line.get("spans", []):
                    span_rect = fitz.Rect(span["bbox"])
                    span_text = span.get("text", "")
                    
                    # Check if this span contains our target text
                    if target_text in span_text and span_rect.intersects(search_rect):
                        # Extract formatting from this span
                        color_int = span.get("color", 0)
                        return {
                            'fontname': self._normalize_fontname(span.get("font", "helv")),
                            'fontsize': span.get("size", 12),
                            'color': self._int_to_rgb(color_int),
                        }
        
        return None
    
    def _int_to_rgb(self, color_int: int) -> tuple[float, float, float]:
        """Convert PyMuPDF integer color to RGB tuple (0-1 range)."""
        # PyMuPDF stores colors as integers in BGR format
        # Extract RGB components and normalize to 0-1 range
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return (r, g, b)
    
    def _normalize_fontname(self, font: str) -> str:
        """Normalize font names to PyMuPDF base font names."""
        # PyMuPDF standard fonts: helv, times, courier, symbol, zapfdingbats
        font_lower = font.lower()
        
        # Map common font names to PyMuPDF base fonts
        if 'helvetica' in font_lower or 'arial' in font_lower or 'sans' in font_lower:
            # Check for bold/italic variants
            if 'bold' in font_lower and 'oblique' in font_lower or 'bold' in font_lower and 'italic' in font_lower:
                return 'hebo'  # Helvetica-BoldOblique
            elif 'bold' in font_lower:
                return 'hebo'  # Helvetica-Bold
            elif 'oblique' in font_lower or 'italic' in font_lower:
                return 'heit'  # Helvetica-Oblique
            return 'helv'
        elif 'times' in font_lower or 'serif' in font_lower:
            if 'bold' in font_lower and 'italic' in font_lower:
                return 'tibi'  # Times-BoldItalic
            elif 'bold' in font_lower:
                return 'tibo'  # Times-Bold
            elif 'italic' in font_lower:
                return 'tii t'  # Times-Italic
            return 'tiro'  # Times-Roman
        elif 'courier' in font_lower or 'mono' in font_lower:
            if 'bold' in font_lower and 'oblique' in font_lower or 'bold' in font_lower and 'italic' in font_lower:
                return 'cobo'  # Courier-BoldOblique
            elif 'bold' in font_lower:
                return 'cobo'  # Courier-Bold
            elif 'oblique' in font_lower or 'italic' in font_lower:
                return 'coit'  # Courier-Oblique
            return 'cour'  # Courier
        
        # Default to Helvetica
        return 'helv'
