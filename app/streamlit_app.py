"""
Streamlit application to visualize media consumption data.
"""

import json
import logging
import os
import streamlit as st

logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app/app.log",
    filemode="w",
)


def load_media_entries(file_path="preprocessing/processed_data/media_entries.json"):
    """
    Load media entries from the JSON file.

    Args:
        file_path: Path to the media entries JSON file

    Returns:
        List of media entry dictionaries
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            st.error(f"File not found: {file_path}")
            return []
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON from {file_path}")
        logger.error("JSON decode error: %s", e)
        return []


def main():
    """Main Streamlit application."""

    # Set page title and header
    st.set_page_config(page_title="Media Timeline", page_icon="📚", layout="wide")

    st.title("Media Timeline")
    st.subheader("Interactive Visualization of Media Consumption")

    # Add a reload button
    if st.button("Reload Data"):
        st.cache_data.clear()
        st.rerun()

    # Load and display the media entries
    media_entries = load_media_entries()

    if media_entries:
        st.write(f"Loaded {len(media_entries)} media entries")
        st.json(media_entries)
    else:
        st.warning("No media entries found. Please run the preprocessing script first.")


if __name__ == "__main__":
    main()
