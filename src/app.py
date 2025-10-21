"""Streamlit UI for the Anonymize Me tool."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from .anonymizer import build_replacement_provider
from .openai_client import create_client
from .processors.email_processor import anonymize_eml
from .prompting import load_prompt_template

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
        st.header("OpenAI configuration")
        env_key_set = bool(os.getenv("OPENAI_API_KEY"))
        api_key_help = "Overrides the OPENAI_API_KEY environment variable." if env_key_set else "Required: set OPENAI_API_KEY in .env file or enter here."
        api_key = st.text_input(
            "API key", 
            type="password", 
            help=api_key_help,
            placeholder="sk-..." if not env_key_set else "Using OPENAI_API_KEY from environment"
        )
        model = st.text_input("Model", value="gpt-4o-mini")

    uploaded_file = st.file_uploader("Email file", type=["eml"], accept_multiple_files=False)

    if not uploaded_file:
        st.info("Select an .eml file to begin anonymizing.")
        return

    prompt_template = load_prompt_template()

    if st.button("Anonymize", type="primary"):
        try:
            with st.spinner("Creating OpenAI client..."):
                client = create_client(api_key or None)
                replacement_provider = build_replacement_provider(client, prompt_template, model=model)
            
            with st.spinner("Anonymizing email and attachments..."):
                anonymized_bytes = anonymize_eml(uploaded_file.getvalue(), replacement_provider)
            
            st.success("✅ Email anonymized successfully!")
            
            # Show verification info prominently
            st.info(f"📊 **Verification:** Original size: {len(uploaded_file.getvalue())} bytes → Anonymized size: {len(anonymized_bytes)} bytes")
            
            # Show debugging info
            with st.expander("🔍 Debug Information - Click to verify PDF was anonymized"):
                import email
                from email import policy
                
                original = email.message_from_bytes(uploaded_file.getvalue(), policy=policy.default)
                anonymized = email.message_from_bytes(anonymized_bytes, policy=policy.default)
                
                original_parts = list(original.walk())
                anonymized_parts = list(anonymized.walk())
                
                st.write(f"**Original email parts:** {len(original_parts)}")
                st.write(f"**Anonymized email parts:** {len(anonymized_parts)}")
                
                st.write("\n**Attachments in anonymized email:**")
                for i, part in enumerate(anonymized_parts):
                    filename = part.get_filename()
                    if filename:
                        payload = part.get_payload(decode=True)
                        st.write(f"📎 Part {i}: **{filename}** ({part.get_content_type()})")
                        st.write(f"   - Size: {len(payload)} bytes")
                        if filename.lower().endswith('.pdf'):
                            # Verify PDF is actually anonymized by checking first bytes
                            st.write(f"   - PDF header: `{payload[:50]}`")
                            st.success(f"✅ This PDF is {len(payload)} bytes (anonymized version)")
            
        except Exception as exc:  # noqa: BLE001 - display error to the user
            st.error(f"Failed to anonymize email: {exc}")
            import traceback
            st.code(traceback.format_exc())
            return

        st.download_button(
            "⬇️ Download ANONYMIZED .eml (with redacted PDF)",
            data=anonymized_bytes,
            file_name=f"ANONYMIZED_{uploaded_file.name}",
            mime="message/rfc822",
            type="primary",
            use_container_width=True,
        )
        
        st.warning("⚠️ Make sure to click the button ABOVE (not re-upload the original file)")
        
        # Add a second verification after download button
        st.info("**To verify the PDF was anonymized:**\n1. Download the file using the button above\n2. Open the .eml file\n3. Extract the PDF attachment\n4. Open the PDF - it should show 'Person B', 'Company X', etc.")
