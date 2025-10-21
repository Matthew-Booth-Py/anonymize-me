# Anonymize Me

Streamlit application that scrubs PII from `.eml` email messages and their supported attachments (PDF and DOCX).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
- An OpenAI API key with access to the specified model (defaults to `gpt-4o-mini`)

## Getting started

```bash
uv sync


```

The application prompts for an OpenAI API key in the sidebar. You can also export `OPENAI_API_KEY` before launching the app.

## How it works

- Email bodies and headers are anonymized with the configured OpenAI model
- PDF attachments are processed using PyMuPDF (fitz), which directly edits the raw PDF content while preserving the original structure
- Word attachments are rewritten in-place via `python-docx`

Add new processors under `src/anonymize_me/processors/` to extend the supported file formats.
