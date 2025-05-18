# Media Timeline Interactive Visualization — Developer Specification

A comprehensive, developer-ready blueprint for building a local interactive application that visualizes weekly media consumption over multiple years.

---

## 1. Overview

Build a local interactive application to visualize weekly media consumption—including TV shows, movies, video games, and books—over multiple years. Data is provided as a raw CSV; a preprocessing script will extract and structure media entries into JSON. The Streamlit (or Plotly Dash) app will render a continuous vertical, week-by-week timeline with color‑coded bars, filters, and a search function.

---

## 2. Functional Requirements

### 2.1 Data Ingestion & Preprocessing

- **Input**: Raw CSV (`media_enjoyed.csv`) with columns:
  - `DateRange` (e.g., "Feb 1–6"; may omit the year on some rows)
  - `Notes` (unstructured text, e.g., "Started playing Hades & Finished FF7")
  - Additional count columns (ignored)
- **Output**: Structured JSON (`media_entries.json`) with one object per media entry:
  ```json
  {
    "title": "Final Fantasy VII Remake",
    "canonical_title": "Final Fantasy VII Remake",
    "type": "Game",
    "start_date": "2023-02-14",
    "finish_date": "2023-03-07",
    "duration_days": 21,
    "status": "completed",
    "tags": {
      "genre": ["JRPG", "Adventure"],
      "platform": ["PS5"],
      "mood": ["Epic"]
    },
    "confidence": 0.92,
    "raw_text": "Finished FF7",
    "warnings": []
  }
  ```
- **Extraction logic**:
  1. Apply light NLP pattern matching for phrases like `Started`, `Finished`, `Watched`, `Started playing`.
  2. Split multiple items per note into separate entries.
  3. Propagate the year forward when missing.
  4. Normalize titles case‑insensitively and apply canonical names via API lookups.
- **Tagging**:
  - Query external APIs using environment variables:
    - `TMDB_API_KEY` for movies/TV shows
    - `IGDB_API_KEY` for video games
    - `OPENLIBRARY_API_KEY` or Google Books API for books
  - Fetch metadata: type, genre, platform, mood (if available).
- **Ambiguity handling**:
  - Compute match confidence; log warnings in the console and `preprocess.log` for:
    - Low-confidence matches
    - Entries missing a start or finish date
  - Support a `hints.yaml` file for manual overrides:
    ```yaml
    FF7:
      canonical_title: "Final Fantasy VII Remake"
      type: "Game"
      tags:
        platform: ["PS5"]
    ```
- **Statistics summary** (printed/logged):
  - Weeks parsed
  - Media entries extracted
  - Counts by media type
  - Number of ambiguous entries
  - Start-only and finish-only counts
  - Count of entries resolved via hints

### 2.2 Interactive Timeline App

- **Framework**: Streamlit (preferred) or Plotly Dash
- **Data Loading**: Read from `media_entries.json`; include a "Reload Data" button
- **Layout**:
  - **Vertical continuous** timeline, displaying every week sequentially
  - **Year dividers** with clear labels and alternating background shades
  - **Bar-based blocks** spanning from start to finish week
    - **Fade-out** gradient for in-progress (start-only) entries over 8–12 weeks
    - **Fade-in** gradient for finish-only entries over the prior 12 weeks
    - Entries longer than 8 months split into separate fade-out and fade-in segments
  - **Horizontal stacking** for multiple entries in the same week
- **UI Elements**:
  - **Dark theme**: slate/charcoal background, subtle gridlines
  - **Color palette**: distinct accent colors per media type or selected tag
  - **Filters**:
    - Checkboxes for media types (TV, Movie, Game, Book)
    - Multi‑select dropdowns for genre, platform, and mood
  - **Search Bar**: live filtering by title (case-insensitive)
  - **Tooltips** on hover, displaying:
    - Raw `Notes` text
    - Canonical title and media type
    - Start and finish dates
    - Duration (in days or weeks)
    - Tags (genre, platform, mood)
- **Performance**: optimize for smooth scrolling with approximately 300 entries
- **Config Parameters** (defined in code with clear labels):
  - Fade durations (in weeks)
  - Maximum bar thickness and spacing
  - Color assignments per tag category
  - Year divider styling

---

## 3. Architecture & Directory Structure

```
media-timeline/
├── .gitignore             # exclude raw CSV and preprocessed JSON
├── requirements.txt       # dependencies: click, requests, streamlit, pydantic, nltk/spacy
├── preprocessing
|   ├── hints.yaml         # versioned manual overrides
|   ├── preprocess.py      # data extraction & tagging script
|   ├── media_entries.json # generated structured data (ignored)
|   └── preprocess.log     # generated on run
└── app/
    ├── streamlit_app.py   # main visualization UI
    └── assets/            # icons, CSS, etc.
```

---

## 4. Error Handling & Logging

- **Preprocess script**:
  - Catch and retry API failures (up to 2 retries with exponential backoff)
  - On persistent API failure, set `tags: {}` and `confidence: 0`; log a warning
  - Validate that `start_date` ≤ `finish_date`; swap dates or log an error if violated
- **App**:
  - Gracefully handle missing or malformed JSON; display a user-friendly error message
  - Fallback to a minimal timeline view if tags are missing

---

## 5. Testing Plan

### 5.1 Unit Tests (preprocess.py)

- Parsing logic for single-entry and multi-entry notes with varied phrasing
- Year propagation and date normalization
- Title normalization and hint overrides
- API tagging with mocked responses
- Duration and fade date calculations
- Accuracy of the statistics summary

### 5.2 Integration Tests

- End-to-end preprocess on a sample CSV; assert JSON output matches expected structure
- Verify hints file overrides are applied correctly

### 5.3 UI Tests (Manual or Automated)

- Filter and search functionality
- Tooltip content accuracy
- Layout integrity: continuous vertical flow, correct year dividers, proper stacking
- Performance: smooth scrolling with approximately 300 entries

### 5.4 Manual QA

- Verify raw `Notes` text appears in tooltips
- Confirm ambiguous entries are logged in `preprocess.log`
- Visual inspection under the dark theme across different screen sizes

---

## 6. Next Steps & Milestones

1. **Initialize the repository** and install dependencies
2. **Implement `preprocess.py`** and write unit tests
3. **Define the JSON schema** and create sample output
4. **Scaffold the Streamlit app** with the basic timeline layout
5. **Add filtering, search, and tooltips**
6. **Refine the UI theme** and optimize performance
7. **Conduct QA and finalize documentation** (including a README)

---

*This polished specification serves as an actionable blueprint for developers to begin implementation immediately.*
