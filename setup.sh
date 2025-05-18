#!/bin/bash

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Export API key placeholders
export TMDB_API_KEY="your_tmdb_api_key_here"
export IGDB_API_KEY="your_igdb_api_key_here"
export OPENLIBRARY_API_KEY="your_openlibrary_api_key_here"

echo "Setup complete! Virtual environment created and dependencies installed."
echo "API key placeholders have been exported for this session."
echo "To make these permanent, add them to your shell profile or .env file."
