"""Pydantic schemas for structured outputs from OpenAI."""

from __future__ import annotations

from pydantic import BaseModel


class SyntheticDataResponse(BaseModel):
    """Schema for synthetic data generation response from OpenAI.
    
    Maps anonymization tags to synthetic replacement values.
    """
    
    replacements: dict[str, str]

