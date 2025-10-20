"""Streamlit UI for the Anonymize Me tool."""

from __future__ import annotations

import streamlit as st

from .anonymizer import build_text_anonymizer
from .email_processing import anonymize_eml
from .openai_client import create_client
from .prompting import load_prompt_template


def build_app() -> None:
    """Render the Streamlit interface."""

    st.set_page_config(page_title="Anonymize Me", page_icon="🛡️", layout="centered")
    st.title("🛡️ Anonymize Me")
    st.write(
        "Upload an .eml email file and we'll anonymize any PII found in the message body and supported attachments."
    )

    with st.sidebar:
        st.header("OpenAI configuration")
        api_key = st.text_input("API key", type="password", help="Overrides the OPENAI_API_KEY environment variable.")
        model = st.text_input("Model", value="gpt-4o-mini")

    uploaded_file = st.file_uploader("Email file", type=["eml"], accept_multiple_files=False)

    if not uploaded_file:
        st.info("Select an .eml file to begin anonymizing.")
        return

    prompt_template = load_prompt_template()

    if st.button("Anonymize", type="primary"):
        try:
            client = create_client(api_key or None)
            text_anonymizer = build_text_anonymizer(client, prompt_template, model=model)
            anonymized_bytes = anonymize_eml(uploaded_file.getvalue(), text_anonymizer)
        except Exception as exc:  # noqa: BLE001 - display error to the user
            st.error(f"Failed to anonymize email: {exc}")
            return

        st.success("Email anonymized successfully.")
        st.download_button(
            "Download anonymized .eml",
            data=anonymized_bytes,
            file_name=f"anonymized_{uploaded_file.name}",
            mime="message/rfc822",
        )
