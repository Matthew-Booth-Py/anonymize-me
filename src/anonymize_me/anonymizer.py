"""Core anonymization logic shared across file handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from openai import OpenAI


class TextProvider(Protocol):
    """Protocol describing callables that anonymize chunks of text."""

    def __call__(self, text: str, *, context: str | None = None) -> str:
        """Return the anonymized version of ``text``."""


@dataclass(slots=True)
class OpenAIAnonymizer:
    """Thin wrapper around the OpenAI Responses API for anonymization."""

    client: OpenAI
    prompt_template: str
    model: str = "gpt-4o-mini"

    def __call__(self, text: str, *, context: str | None = None) -> str:
        if not text:
            return ""

        system_prompt = self.prompt_template.strip()
        if context:
            system_prompt = f"{system_prompt}\n\nContext: {context.strip()}"

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
        )
        return response.output_text.strip()


def build_text_anonymizer(client: OpenAI, prompt_template: str, model: str = "gpt-4o-mini") -> TextProvider:
    """Return a callable that anonymizes text using OpenAI."""

    anonymizer = OpenAIAnonymizer(client=client, prompt_template=prompt_template, model=model)
    return anonymizer
