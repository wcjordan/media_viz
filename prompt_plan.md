# Prompt Plan for Media Timeline Interactive Visualization

This document provides a structured, test-driven series of prompts for a code-generation LLM to implement the Media Timeline project. Each prompt builds on the previous one, ensuring incremental progress and integrated testing.

---

## 1. High-Level Blueprint

1. **Repository & Environment Setup**  
   - Initialize a Git repository.  
   - Create a `.gitignore` excluding generated and sensitive files.  
   - Configure a Python virtual environment and list core dependencies (`streamlit`, `requests`, `pydantic`, `pytest`, `spacy`).
2. **Preprocessing Core**  
   - Load and parse the raw CSV, propagating missing years.  
   - Extract media entries using light NLP (e.g., “Started X”, “Finished Y”).  
   - Normalize titles, apply canonical names via TMDB/IGDB/Open Library APIs.  
   - Support manual overrides through a `hints.yaml` file.  
   - Output structured JSON and log processing statistics.
3. **Schema & Test Harness**  
   - Define data models using Pydantic.  
   - Write unit tests for each preprocessing component.
4. **Timeline App Skeleton**  
   - Build a minimal Streamlit application to load and display JSON data.  
   - Add a “Reload Data” control.
5. **Bar-Based Visualization**  
   - Render week-by-week bars with fade logic for in-progress or lead-in entries.  
   - Implement horizontal stacking for concurrent entries.
6. **Interactive Features & Styling**  
   - Add filters (media type, genre, platform, mood) and a search bar.  
   - Display hover tooltips with full metadata.  
   - Apply a minimal dark theme with year dividers and accent colors.
7. **Integration & Documentation**  
   - Write end-to-end tests and integration scripts.  
   - Draft comprehensive README and tag the first release.

---

## 2. Chunk Breakdown & Right-Sizing

| Chunk | Purpose                     | Key Steps                                                                                       |
|-------|-----------------------------|-------------------------------------------------------------------------------------------------|
| **A** | Repository & Environment    | Initialize repo; create `.gitignore`; author `requirements.txt`; setup script; initial test stub |
| **B** | CSV Loader & Date Parsing   | Read CSV; infer missing years; parse `DateRange` into ISO dates; write loader tests            |
| **C** | NLP Extraction Engine       | Split `Notes`; detect actions (`Started`, `Finished`, `Watched`); write extractor tests         |
| **D** | API Tagger & Hints          | Stub API calls; load `hints.yaml`; apply overrides; write tagging tests                         |
| **E** | JSON Schema & Validation    | Define Pydantic models; serialize to JSON; write model validation tests                         |
| **F** | Streamlit Skeleton          | Load and display raw JSON; add “Reload Data” button; write a smoke test                          |
| **G** | Bar Layout & Fading Logic   | Compute weekly grid; render bars with fade rules; write layout tests                            |
| **H** | Filters & Search            | Add UI widgets; implement filtering logic; write filter tests                                    |
| **I** | Tooltips & Styling          | Implement hover tooltips; apply dark theme and year dividers; perform manual QA                 |
| **J** | Integration & Documentation | Create run script; write end-to-end tests; draft `README.md`; tag release                       |

---

## 3. Test-Driven LLM Prompts

Below are ten sequential prompts. Each prompt instructs the LLM to write implementation code and accompanying tests. Execute them in order.

### Prompt 1: Repository & Environment Setup  
```text
Initialize the Media Timeline project:
1. Create a Git repository.
2. Add a `.gitignore` excluding `media_entries.json`, raw CSVs, and `preprocess.log`.
3. Generate `requirements.txt` with: streamlit, requests, pydantic, pytest, spacy.
4. Write `setup.sh` to:
   - Create a Python virtual environment.
   - Install dependencies.
   - Export placeholders for TMDB_API_KEY, IGDB_API_KEY, OPENLIBRARY_API_KEY.
5. Create `tests/test_setup.py` with a dummy test that always passes.
```

### Prompt 2: CSV Loader & Year Propagation  
```text
In `preprocess.py`:
- Implement `load_weekly_records(path: str) -> List[Dict]`:
  - Read `media_enjoyed.csv`.
  - Parse `DateRange` into `start_date` and `end_date` (YYYY-MM-DD), inferring missing years.
  - Return a list of dicts containing `start_date`, `end_date`, and `raw_notes`.

Write pytest tests in `tests/test_loader.py` to verify:
- Correct ISO date parsing.
- Accurate year propagation.
```

### Prompt 3: NLP Extraction Engine  
```text
Extend `preprocess.py` with:
- `extract_entries(record: Dict) -> List[Dict]`:
  - Split `raw_notes` on `&` or newlines.
  - Use regex or spaCy to detect actions (`started`, `finished`, `watched`).
  - Return entries with `raw_text`, `action`, and `week_date`.

Write pytest tests in `tests/test_extractor.py` for:
- Single and multiple entry parsing.
- Various phrasings of start/finish/watch actions.
```

### Prompt 4: API Tagger & Hints Support  
```text
Create `tagger.py`:
- Load `hints.yaml` for manual overrides.
- Implement stub functions:
  - `query_tmdb(title: str) -> (canonical_title, metadata, confidence)`
  - `query_igdb(...)` and `query_openlibrary(...)`.
- Write `apply_tagging(entries: List[Dict]) -> List[Dict]`:
  - Apply hints first, then API calls.
  - Attach `type`, `tags` (genre, platform, mood), and `confidence`.

Write tests in `tests/test_tagger.py` using mocked API responses and hint scenarios.
```

### Prompt 5: JSON Schema & Validation  
```text
In `models.py`, define Pydantic:
- `MediaEntry` model matching the JSON specification.

In `preprocess.py`:
- Validate tagged entries against `MediaEntry`.
- Serialize to `media_entries.json`.

Write tests in `tests/test_models.py` to ensure:
- Model instantiation with valid data.
- Correct JSON output structure.
```

### Prompt 6: Streamlit Skeleton  
```text
In `app/streamlit_app.py`:
- Load `media_entries.json`.
- Display a header and JSON dump with `st.json()`.
- Add a "Reload Data" button to refresh the data display.

Write a smoke test in `tests/test_app.py` to assert the app imports and runs without errors.
```

### Prompt 7: Bar Layout & Fading Logic  
```text
In `app/streamlit_app.py`:
- Compute a continuous vertical axis of weeks using Pandas or dateutil.
- Map each `MediaEntry` to:
  - X-position (week index).
  - Length (# of weeks).
  - Fade parameters for in-progress and lead-in entries.
- Render bars via Streamlit’s `st.plotly_chart` with a dark theme.

Add tests in `tests/test_layout.py` to verify:
- Correct bar positions and lengths.
- Proper opacity values for fade logic.
```

### Prompt 8: Filters & Search  
```text
Enhance `streamlit_app.py`:
- Add widgets:
  - Multi-select for `type`, `genre`, `platform`, `mood`.
  - Text input for title search.
- Filter entries based on widget inputs before rendering.

Write tests in `tests/test_filters.py` to confirm filtering logic accuracy.
```

### Prompt 9: Tooltips & Styling  
```text
In `streamlit_app.py`:
- Add hover tooltips showing:
  - Raw `Notes` text.
  - Canonical title, dates, duration, and tags.
- Apply dark CSS settings:
  - Slate background, subtle gridlines, accent colors.

Include a snapshot test in `tests/test_ui_snapshot.py` capturing a minimal rendering.
```

### Prompt 10: Integration & Documentation  
```text
- Write `scripts/run_all.sh` to:
  1. Run `preprocess.py` on a sample CSV.
  2. Launch the Streamlit app.
- Add `tests/test_integration.py` to:
  1. Programmatically call `preprocess.py`.
  2. Import and instantiate the Streamlit app.
- Draft `README.md` with:
  - Project overview.
  - Setup and usage instructions.
  - Testing guide.
- Tag version `v0.1.0` in Git.
```

---

*All prompts are designed for test-first, incremental development. Good luck!*