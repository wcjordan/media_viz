"""
Streamlit application to visualize media consumption data.
"""

import logging

import streamlit as st

from app.media_entries import load_media_entries, extract_timeline_spans
from app.timeline_chart import create_timeline_chart
from app.timeline_data import prepare_timeline_data
from app.utils import is_debug_mode


logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.DEBUG if is_debug_mode() else logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app/app.log",
    filemode="w",
)


def main():
    """Main Streamlit application."""

    # Set page title and header
    st.set_page_config(
        page_title="Media Timeline", page_icon=":umbrella:", layout="wide"
    )

    # Add a reload button
    if st.button("Reload Data"):
        st.cache_data.clear()
        st.rerun()

    # Load and display the media entries
    media_entries = load_media_entries()

    if media_entries:
        # Prepare data for timeline
        spans, min_date, max_date = extract_timeline_spans(media_entries)
        weeks_df, bars_df = prepare_timeline_data(spans, min_date, max_date)

        # Create and display timeline chart
        fig = create_timeline_chart(weeks_df, bars_df)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("No media entries found. Please run the preprocessing script first.")


if __name__ == "__main__":
    main()
