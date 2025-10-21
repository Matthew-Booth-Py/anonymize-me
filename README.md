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
  - Person names → `Person A`, `Person B`, etc.
  - Email addresses → `persona@example.com`, `personb@example.com`, etc.
  - Phone numbers → `555-000-0001`, `555-000-0002`, etc.
  - Locations → `City A`, `City B`, etc.
  - SSNs, credit cards, IP addresses, URLs, bank numbers, and more

- **Customizable Detection**: Select which entity types to anonymize via the sidebar (default: Person, Email, Phone, Location, SSN, Credit Card)

- **Consistent Replacements**: The same PII value always gets the same replacement across all email parts and attachments

- **File Processing**:
  - Email bodies and headers are anonymized using text replacement
  - PDF attachments analyze their own content and apply redactions using PyMuPDF
  - Word attachments analyze their own content and apply replacements via `python-docx`
  - All attachments share the same replacement cache for consistency

## Extending

Add new processors under `src/processors/` to extend the supported file formats. Each processor should accept a `ReplacementProvider` callable that returns a dictionary mapping original PII to anonymized replacements.

## Why Presidio?

Unlike LLM-based approaches, Presidio:
- Works offline (no API keys required)
- Provides deterministic, consistent results
- Supports multiple languages and entity types out of the box
- Is faster and more cost-effective for PII detection
