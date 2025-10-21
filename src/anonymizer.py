"""Core anonymization logic shared across file handlers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel, Field


class ReplacementPair(BaseModel):
    """A single PII replacement mapping."""
    
    original: str = Field(description="The original PII value to be replaced")
    replacement: str = Field(description="The anonymized replacement value")


class PIIReplacements(BaseModel):
    """Pydantic model for PII replacement mappings."""
    
    replacements: list[ReplacementPair] = Field(
        default_factory=list,
        description="List of PII replacement mappings"
    )


class ReplacementProvider(Protocol):
    """Protocol describing callables that generate PII replacement mappings."""

    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        """Return a dictionary mapping original PII to anonymized replacements."""


@dataclass(slots=True)
class OpenAIAnonymizer:
    """OpenAI-based anonymizer using structured outputs with Pydantic."""

    client: OpenAI
    prompt_template: str
    model: str = "gpt-4o-mini"

    def __call__(self, text: str, *, context: str | None = None) -> dict[str, str]:
        if not text or not text.strip():
            return {}

        system_prompt = self.prompt_template.strip()
        if context:
            system_prompt = f"{system_prompt}\n\nContext: {context.strip()}"

        try:
            # Use structured outputs with Pydantic model
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
                response_format=PIIReplacements,
                temperature=0.3,  # Low temperature for consistent replacements
            )
            
            result = completion.choices[0].message.parsed
            
            if result is None:
                return {}
            
            # Convert list of ReplacementPair to dict
            replacements_dict = {pair.original: pair.replacement for pair in result.replacements}
            
            return replacements_dict
            
        except Exception as e:
            # Silently return empty dict on error
            return {}


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Apply replacement mappings to text, preserving structure and formatting.
    
    Replacements are applied in order of longest key first to avoid partial replacements.
    """
    if not replacements or not text:
        return text
    
    # Sort by length (longest first) to avoid partial replacements
    sorted_items = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
    
    result = text
    replacements_made = 0
    
    for original, replacement in sorted_items:
        if original in result:
            # Use regex with word boundaries for more accurate replacement
            # Escape special regex characters in the original string
            pattern = re.escape(original)
            result = re.sub(pattern, replacement, result)
    
    return result


def build_replacement_provider(
    client: OpenAI, 
    prompt_template: str, 
    model: str = "gpt-4o-mini"
) -> ReplacementProvider:
    """Return a callable that generates replacement mappings using OpenAI."""
    anonymizer = OpenAIAnonymizer(client=client, prompt_template=prompt_template, model=model)
    return anonymizer
