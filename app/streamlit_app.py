import json
import os
import streamlit as st

def load_media_entries(file_path="preprocessing/media_entries.json"):
    """
    Load media entries from the JSON file.
    
    Args:
        file_path: Path to the media entries JSON file
        
    Returns:
        List of media entry dictionaries
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        else:
            st.error(f"File not found: {file_path}")
            return []
    except Exception as e:
        st.error(f"Error loading media entries: {str(e)}")
        return []

def main():
    """Main Streamlit application."""
    
    # Set page title and header
    st.set_page_config(
        page_title="Media Timeline",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("Media Timeline")
    st.subheader("Interactive Visualization of Media Consumption")
    
    # Add a reload button
    if st.button("Reload Data"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    # Load and display the media entries
    media_entries = load_media_entries()
    
    if media_entries:
        st.write(f"Loaded {len(media_entries)} media entries")
        st.json(media_entries)
    else:
        st.warning("No media entries found. Please run the preprocessing script first.")

if __name__ == "__main__":
    main()
