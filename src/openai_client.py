"""Helpers for working with the OpenAI client."""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI


def create_client(api_key: Optional[str] = None) -> OpenAI:
    """Instantiate an OpenAI client using the provided API key or environment variable."""
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "An OpenAI API key is required. Set the OPENAI_API_KEY environment variable or "
            "provide the key explicitly."
        )
    return OpenAI(api_key=key)
