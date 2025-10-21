"""Test script to debug anonymization of email with PDF attachment."""

from pathlib import Path
from email import message_from_bytes

# Import the processors
from src.processors.email_processor import EmailProcessor
from src.anonymizer import build_replacement_provider


def main():
    # Setup
    email_file = "Resume for Matthew Booth.eml"

    print("=" * 80)
    print(f"Testing anonymization of: {email_file}")
    print("=" * 80)

    # Load email
    with open(email_file, "rb") as f:
        email_bytes = f.read()

    print(f"\n[OK] Loaded email: {len(email_bytes)} bytes")

    # Build replacement provider (using Presidio)
    replacement_provider = build_replacement_provider()

    print("[OK] Created Presidio replacement provider")

    # Create email processor
    processor = EmailProcessor(replacement_provider)

    print("\n" + "=" * 80)
    print("PROCESSING EMAIL")
    print("=" * 80)

    # Process the email (only pass the bytes, not the filename)
    result_bytes = processor.anonymize(email_bytes)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nAnonymized email size: {len(result_bytes)} bytes")
    print(f"Original email size: {len(email_bytes)} bytes")

    # Parse the anonymized email to check content
    anonymized_msg = message_from_bytes(result_bytes)

    print("\n" + "-" * 80)
    print("EMAIL HEADERS:")
    print("-" * 80)
    print(f"From: {anonymized_msg.get('From')}")
    print(f"To: {anonymized_msg.get('To')}")
    print(f"Subject: {anonymized_msg.get('Subject')}")

    # Check body
    print("\n" + "-" * 80)
    print("EMAIL BODY:")
    print("-" * 80)

    if anonymized_msg.is_multipart():
        for part in anonymized_msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                print(body)
                print()

                # Check if PII was replaced
                pii_checks = [
                    ("Matthew Booth", "Should be replaced"),
                    ("Matt", "Should be replaced"),
                    ("Person A", "Should be present (replacement)"),
                    ("Person B", "Should be present (replacement)"),
                    ("mbooth", "Should be replaced"),
                ]

                print("\n" + "-" * 80)
                print("PII CHECK IN BODY:")
                print("-" * 80)
                for text, description in pii_checks:
                    if text in body:
                        print(f"[YES] FOUND '{text}' - {description}")
                    else:
                        print(f"[NO] NOT FOUND '{text}' - {description}")

    else:
        body = anonymized_msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        print(body[:500])

    # Check attachments
    print("\n" + "-" * 80)
    print("ATTACHMENTS:")
    print("-" * 80)

    attachment_count = 0
    for part in anonymized_msg.walk():
        filename = part.get_filename()
        if filename:
            attachment_count += 1
            print(f"\n{attachment_count}. {filename}")
            print(f"   Type: {part.get_content_type()}")

            # If it's a PDF, save it for manual inspection
            if filename.endswith(".pdf"):
                pdf_bytes = part.get_payload(decode=True)
                output_path = f"test_output_{filename}"
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)
                print(f"   Saved to: {output_path} ({len(pdf_bytes)} bytes)")

                # Try to read the PDF text
                try:
                    import fitz

                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    text = ""
                    for page_num in range(len(doc)):
                        text += doc[page_num].get_text()
                    doc.close()

                    print(f"\n   PDF Text Content (first 500 chars):")
                    print(f"   {text[:500]}")

                    # Check for PII in PDF
                    print(f"\n   PII CHECK IN PDF:")
                    pdf_pii_checks = [
                        ("Matthew Booth", "Should be replaced"),
                        ("Person A", "Should be present (replacement)"),
                        ("Person B", "Should be present (replacement)"),
                        ("mbooth", "Should be replaced"),
                        ("persona@example.com", "Should be present (replacement)"),
                        ("City A", "Should be present (replacement)"),
                    ]

                    for text_to_find, description in pdf_pii_checks:
                        if text_to_find in text:
                            print(f"   [YES] FOUND '{text_to_find}' - {description}")
                        else:
                            print(f"   [NO] NOT FOUND '{text_to_find}' - {description}")

                except Exception as e:
                    print(f"   Error reading PDF: {e}")

    if attachment_count == 0:
        print("No attachments found")

    # Save the full anonymized email
    output_email_path = "test_output_email.eml"
    with open(output_email_path, "wb") as f:
        f.write(result_bytes)

    print(f"\n[OK] Saved anonymized email to: {output_email_path}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
