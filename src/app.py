"""Streamlit UI for the Anonymize Me tool."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from .anonymizer import build_replacement_provider
from .processors.email_processor import anonymize_eml
from .synthetic_data import fill_anonymized_email

# Load environment variables from .env file
load_dotenv()


def build_app() -> None:
    """Render the Streamlit interface."""

    st.set_page_config(page_title="Anonymize Me", page_icon="🛡️", layout="centered")
    st.title("🛡️ Anonymize Me")
    st.write(
        "Upload an .eml email file and we'll anonymize any PII found in the message body and supported attachments."
    )

    with st.sidebar:
        st.header("About")
        st.info(
            "🔒 **Using Presidio for PII Detection**\n\n"
            "- Works offline - no API keys required\n"
            "- Powered by spaCy NLP models\n"
            "- Supports 17+ entity types"
        )
        
        st.header("OpenAI Settings")
        st.markdown("Optional: Fill anonymized tags with synthetic data using GPT-4o-mini")
        
        # Get API key from environment variable
        env_api_key = os.getenv("OPENAI_API_KEY", "")
        
        # Show status of environment variable
        if env_api_key:
            st.success("✅ OPENAI_API_KEY loaded from .env file")
        
        # Allow override via text input
        openai_api_key = st.text_input(
            "OpenAI API Key (optional override)",
            type="password",
            value=env_api_key,
            help="Loaded from OPENAI_API_KEY in .env file, or enter manually to override",
            key="openai_api_key"
        )

    uploaded_file = st.file_uploader(
        "Email file", type=["eml"], accept_multiple_files=False
    )

    # Entity type selection table
    st.subheader("Select Entity Types to Anonymize")

    # Define entity types with descriptions
    entity_data = [
        {
            "Entity Type": "PERSON",
            "Description": "A person's full name (first, middle, last etc)",
        },
        {
            "Entity Type": "EMAIL_ADDRESS",
            "Description": "An email address (RFC-822 style)",
        },
        {"Entity Type": "PHONE_NUMBER", "Description": "A telephone number"},
        {
            "Entity Type": "LOCATION",
            "Description": "Geographic locations (cities/provinces/countries/regions)",
        },
        {
            "Entity Type": "CREDIT_CARD",
            "Description": "A credit card number (12-19 digits)",
        },
        {
            "Entity Type": "US_SSN",
            "Description": "US Social Security Number (9 digits)",
        },
        {"Entity Type": "DATE_TIME", "Description": "Absolute or relative dates/times"},
        {
            "Entity Type": "URL",
            "Description": "A URL pointing to a resource on the Internet",
        },
        {"Entity Type": "IP_ADDRESS", "Description": "An IP address (IPv4 or IPv6)"},
        {
            "Entity Type": "CRYPTO",
            "Description": "Cryptocurrency wallet number (Bitcoin addresses)",
        },
        {
            "Entity Type": "IBAN_CODE",
            "Description": "International Bank Account Number (IBAN)",
        },
        {
            "Entity Type": "NRP",
            "Description": "Nationality, religious or political group",
        },
        {"Entity Type": "MEDICAL_LICENSE", "Description": "A medical licence number"},
        {
            "Entity Type": "US_BANK_NUMBER",
            "Description": "A US bank account number (8-17 digits)",
        },
        {
            "Entity Type": "US_DRIVER_LICENSE",
            "Description": "A US driver's licence number",
        },
        {
            "Entity Type": "US_ITIN",
            "Description": "US Individual Taxpayer ID (9 digits, starts with 9)",
        },
        {"Entity Type": "US_PASSPORT", "Description": "US passport number (9 digits)"},
    ]

    # Default selections (most common PII types)
    default_selected = {
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "US_SSN",
        "CREDIT_CARD",
    }

    # Add checkboxes to each row
    df = pd.DataFrame(entity_data)
    df.insert(0, "Select", df["Entity Type"].isin(default_selected))

    # Display as data editor with checkboxes
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Check to anonymize this entity type",
                default=False,
            ),
            "Entity Type": st.column_config.TextColumn(
                "Entity Type",
                disabled=True,
            ),
            "Description": st.column_config.TextColumn(
                "Description",
                disabled=True,
                width="large",
            ),
        },
        disabled=["Entity Type", "Description"],
        hide_index=True,
        use_container_width=True,
    )

    # Extract selected entity types
    selected_entities = edited_df[edited_df["Select"]]["Entity Type"].tolist()

    # Show selection summary
    if selected_entities:
        st.info(
            f"✓ Selected {len(selected_entities)} entity type(s): {', '.join(selected_entities)}"
        )
    else:
        st.warning("⚠️ No entity types selected. All entity types will be detected.")

    if not uploaded_file:
        st.info("👆 Upload an .eml file to begin anonymizing.")
        return

    # Initialize session state for anonymized data
    if "anonymized_bytes" not in st.session_state:
        st.session_state.anonymized_bytes = None
        st.session_state.selected_entities = None
        st.session_state.uploaded_filename = None
        st.session_state.synthetic_bytes = None

    if st.button("Anonymize", type="primary"):
        # Use None if no entities selected (will detect all types)
        entity_types_to_use = selected_entities if selected_entities else None

        try:
            with st.spinner("Initializing Presidio analyzer..."):
                replacement_provider = build_replacement_provider(
                    entity_types=entity_types_to_use
                )

            with st.spinner("Analyzing and anonymizing email and attachments..."):
                anonymized_bytes = anonymize_eml(
                    uploaded_file.getvalue(), replacement_provider
                )

            # Store in session state
            st.session_state.anonymized_bytes = anonymized_bytes
            st.session_state.selected_entities = selected_entities
            st.session_state.uploaded_filename = uploaded_file.name
            st.session_state.synthetic_bytes = None  # Reset synthetic data

            st.success("✅ Email anonymized successfully!")

            # Show verification info prominently
            st.info(
                f"📊 **Verification:** Original size: {len(uploaded_file.getvalue())} bytes → Anonymized size: {len(anonymized_bytes)} bytes"
            )

        except Exception as exc:  # noqa: BLE001 - display error to the user
            st.error(f"Failed to anonymize email: {exc}")
            import traceback

            st.code(traceback.format_exc())
            return

    # Show download buttons if anonymized data exists
    if st.session_state.anonymized_bytes:
        st.download_button(
            "⬇️ Download ANONYMIZED .eml (with tags)",
            data=st.session_state.anonymized_bytes,
            file_name=f"ANONYMIZED_{st.session_state.uploaded_filename}",
            mime="message/rfc822",
            type="primary",
            use_container_width=True,
        )

        # Show synthetic data generation section
        st.divider()
        st.subheader("🤖 Generate Synthetic Data")
        st.write(
            "Replace anonymized tags (like `<PERSON>`, `<EMAIL_ADDRESS>`) with realistic synthetic data using GPT-4o-mini."
        )

        # Check if API key is provided and not empty
        api_key = st.session_state.get("openai_api_key", "").strip()
        if not api_key:
            st.warning(
                "⚠️ Please enter your OpenAI API key in the sidebar to enable synthetic data generation."
            )
        else:
            if st.button("🎲 Fill with Synthetic Data", type="secondary", use_container_width=True):
                try:
                    with st.spinner("Generating synthetic data with GPT-4o-mini..."):
                        synthetic_bytes = fill_anonymized_email(
                            st.session_state.anonymized_bytes,
                            api_key,  # Use the validated api_key variable
                            st.session_state.selected_entities,
                        )
                        st.session_state.synthetic_bytes = synthetic_bytes

                    st.success("✅ Synthetic data generated successfully!")

                except Exception as exc:  # noqa: BLE001 - display error to the user
                    st.error(f"Failed to generate synthetic data: {exc}")
                    import traceback

                    st.code(traceback.format_exc())

            # Show download button for synthetic version
            if st.session_state.synthetic_bytes:
                st.download_button(
                    "⬇️ Download SYNTHETIC .eml (with fake data)",
                    data=st.session_state.synthetic_bytes,
                    file_name=f"SYNTHETIC_{st.session_state.uploaded_filename}",
                    mime="message/rfc822",
                    type="primary",
                    use_container_width=True,
                )


