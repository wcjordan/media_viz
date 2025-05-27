"""
Streamlit application to visualize media consumption data.
"""

import logging

import streamlit as st

from app.extract_timeline_spans import (
    load_media_entries,
    prepare_timeline_data,
    generate_week_axis,
    generate_bars,
)
from app.timeline_chart import create_timeline_chart


logger = logging.getLogger(__name__)
# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="app/app.log",
    filemode="w",
)


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

        # Create tabs for different views
        tab1, tab2 = st.tabs(["Timeline Visualization", "Raw JSON Data"])

        with tab1:
            # Prepare data for timeline
            spans, min_date, max_date = prepare_timeline_data(media_entries)
            weeks_df = generate_week_axis(min_date, max_date)
            bars_df = generate_bars(spans)

            # Create and display timeline chart
            fig = create_timeline_chart(weeks_df, bars_df)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            # Display raw JSON data
            st.json(media_entries)
    else:
        st.warning("No media entries found. Please run the preprocessing script first.")


if __name__ == "__main__":
    main()
