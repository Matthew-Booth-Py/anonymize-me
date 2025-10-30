"""Synthetic data generation using OpenAI GPT-4o-mini."""

from __future__ import annotations

import json
import re

from openai import OpenAI

from .anonymizer import apply_replacements


def extract_tags_from_text(text: str) -> set[str]:
    """Extract all unique anonymization tags from text.
    
    Args:
        text: Text containing tags like <PERSON>, <EMAIL_ADDRESS>, etc.
        
    Returns:
        Set of unique tags found
    """
    pattern = r"<([A-Z_]+)>"
    matches = re.findall(pattern, text)
    return {f"<{match}>" for match in matches}


def generate_synthetic_data(tags: set[str], context_sample: str, api_key: str) -> dict[str, str]:
    """Use GPT-4o-mini to generate synthetic data for tags.
    
    Args:
        tags: Set of tags to generate data for (e.g., {"<PERSON>", "<EMAIL_ADDRESS>"})
        context_sample: Sample of the document for context
        api_key: OpenAI API key
        
    Returns:
        Dictionary mapping tags to synthetic values
        
    Raises:
        ValueError: If GPT fails to generate data or returns incomplete results
    """
    if not tags:
        return {}
    
    tags_list = sorted(tags)
    
    prompt = f"""Generate realistic but completely fake synthetic data to replace the following anonymization tags.

Tags to replace:
{chr(10).join(f'- {tag}' for tag in tags_list)}

Context sample:
{context_sample[:1500]}

Guidelines:
- Make the data internally consistent (e.g., email should match person's name)
- Use completely fake data that doesn't correspond to any real entity
- For numbers like SSN, credit cards, use valid formats but invalid checksums
- Generate a replacement for EVERY tag listed above

Provide replacements in the 'replacements' field as a dictionary."""

    client = OpenAI(api_key=api_key)
    
    # Call GPT with JSON mode
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a synthetic data generator that creates realistic but fake data for testing. Always respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=1500,
    )

    # Extract and parse the JSON response
    response_text = response.choices[0].message.content
    if not response_text:
        raise ValueError("GPT failed to generate synthetic data - no response returned")
    
    try:
        response_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"GPT returned invalid JSON: {e}")
    
    # Extract replacements from the response
    if "replacements" not in response_data:
        raise ValueError("GPT response missing 'replacements' field")
    
    synthetic_data = response_data["replacements"]
    
    # Ensure all tags have replacements
    missing_tags = tags - set(synthetic_data.keys())
    if missing_tags:
        raise ValueError(f"GPT failed to generate synthetic data for tags: {missing_tags}")
    
    return synthetic_data


class SyntheticReplacementProvider:
    """Replacement provider that returns cached synthetic data mappings.
    
    This acts as a ReplacementProvider that always returns the same
    synthetic mappings, allowing us to reuse EmailProcessor infrastructure.
    """
    
    def __init__(self, synthetic_mappings: dict[str, str]) -> None:
        """Initialize with pre-generated synthetic mappings."""
        self.synthetic_mappings = synthetic_mappings
    
    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        """Return the cached synthetic mappings.
        
        Only returns mappings for tags found in the given text.
        """
        # Extract tags from this text
        tags = extract_tags_from_text(text)
        
        # Return only relevant mappings
        return {tag: self.synthetic_mappings[tag] for tag in tags if tag in self.synthetic_mappings}


def fill_anonymized_email(
    anonymized_bytes: bytes, api_key: str, entity_types: list[str] | None = None
) -> bytes:
    """Fill an anonymized email with synthetic data.
    
    This properly handles email structure and attachments:
    1. Extracts all tags from the anonymized email (including PDFs)
    2. Generates synthetic data for those tags using GPT
    3. Uses EmailProcessor to apply replacements to all parts (body, PDFs, DOCX, etc.)
    
    Args:
        anonymized_bytes: Anonymized email content with tags like <PERSON>
        api_key: OpenAI API key
        entity_types: List of entity types (unused, kept for compatibility)
        
    Returns:
        Email with synthetic data filled in
        
    Raises:
        ValueError: If decoding fails or synthetic data generation fails
    """
    from .processors.email_processor import EmailProcessor
    
    # Convert to text to extract tags
    anonymized_text = anonymized_bytes.decode('utf-8', errors='replace')
    
    # Extract all unique tags
    tags = extract_tags_from_text(anonymized_text)
    
    if not tags:
        raise ValueError("No anonymization tags found in the email")
    
    # Generate synthetic data for all tags (will raise on failure)
    synthetic_mappings = generate_synthetic_data(tags, anonymized_text[:2000], api_key)
    
    # Create a replacement provider with the synthetic mappings
    synthetic_provider = SyntheticReplacementProvider(synthetic_mappings)
    
    # Use EmailProcessor to apply replacements throughout the email structure
    # This handles PDFs, DOCX, HTML, and text correctly
    processor = EmailProcessor(synthetic_provider)
    return processor.anonymize(anonymized_bytes)
