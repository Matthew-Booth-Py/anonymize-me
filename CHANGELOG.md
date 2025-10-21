# Anonymize-Me Changelog

## Latest Changes

### Features Added
- ✅ **Random Attachment Filenames**: All attachment filenames are now randomized using 12-character hex UUIDs
  - PDFs: `5eb8a98251fa.pdf` (instead of `resumt.pdf`)
  - DOCX: `a1b2c3d4e5f6.docx`
  - Other files: Random names with original extensions preserved

### Improvements
- ✅ **Environment Variable Support**: API keys can now be loaded from `.env` files
  - Automatically loads `OPENAI_API_KEY` on startup
  - Added `python-dotenv` dependency
  
- ✅ **Cleaner Output**: Removed excessive debug logging
  - Production-ready console output
  - All debug prints removed from processors

### Bug Fixes
- ✅ **Template Path Fixed**: Corrected template file location for `src/` directory structure
- ✅ **Module Import Fixed**: Restructured from package to simple module layout in `src/`

### Project Structure Changes
- Moved from `src/anonymize_me/` package structure to simple `src/` modules
- Updated all imports to use `from src.module import`
- Removed package build configuration

## How to Use

### Setup
1. Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=sk-your-api-key-here
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Run the Streamlit app:
   ```bash
   uv run python main.py
   ```

### Features
- **Email Body Anonymization**: All PII in email headers and body text replaced
- **PDF Anonymization**: Text redacted and replaced while preserving formatting
- **DOCX Anonymization**: Word documents processed with formatting preserved
- **Random Filenames**: All attachments get random 12-character hex names
- **Consistent Replacements**: Same PII always replaced with same placeholder

### Example Output
**Original Email:**
- From: matthew.booth@company.com
- Attachment: resume.pdf (contains "Matthew Booth", "555-123-4567")

**Anonymized Email:**
- From: persona@example.com
- Attachment: `5eb8a98251fa.pdf` (contains "Person A", "555-000-0000")

---

**Note**: When viewing anonymized emails in Outlook, the client may cache old attachment filenames. The actual .eml file contains the correct random filenames - forward the email or check the file directly to verify.

