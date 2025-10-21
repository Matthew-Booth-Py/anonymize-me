# Anonymize Me

Streamlit application that scrubs PII from `.eml` email messages and their supported attachments (PDF and DOCX).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
- Python 3.11 or higher

## Getting started

1. Install dependencies and sync the environment:

```bash
uv sync
```

2. Download the required spaCy language model:

```bash
uv run python -m spacy download en_core_web_lg
```

3. Run the Streamlit app:

```bash
uv run streamlit run main.py
```

## How it works

This tool uses **Presidio** for PII detection and anonymization:

- **PII Detection**: Uses Presidio's AnalyzerEngine powered by spaCy's `en_core_web_lg` model to detect 17+ entity types:
  - Person names → `<PERSON>`
  - Email addresses → `<EMAIL_ADDRESS>`
  - Phone numbers → `<PHONE_NUMBER>`
  - Locations → `<LOCATION>`
  - SSNs, credit cards, IP addresses, URLs, bank numbers, and more → `<ENTITY_TYPE>`

- **Customizable Detection**: Select which entity types to anonymize via an interactive table (default: Person, Email, Phone, Location, SSN, Credit Card)

- **Generic Replacements**: All detected PII is replaced with `<ENTITY_TYPE>` format (e.g., `<PERSON>`, `<EMAIL_ADDRESS>`)

- **File Processing**:
  - **Email bodies**: Plain text and HTML bodies are anonymized
    - HTML: Text content and attributes (href, src, etc.) are anonymized while preserving HTML structure
    - Plain text: Direct text replacement
  - **PDF attachments**: Analyzed independently and redacted using PyMuPDF
  - **DOCX attachments**: Analyzed independently with replacements applied via `python-docx`
  - Each part is processed independently with generic entity type placeholders

## Extending

Add new processors under `src/processors/` to extend the supported file formats. Each processor should accept a `ReplacementProvider` callable that returns a dictionary mapping original PII to anonymized replacements.

## Why Presidio?

Unlike LLM-based approaches, Presidio:
- Works offline (no API keys required)
- Provides deterministic, consistent results
- Supports multiple languages and entity types out of the box
- Is faster and more cost-effective for PII detection
