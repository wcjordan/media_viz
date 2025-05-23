# TODO List for Media Timeline Project

## 1. Repository & Environment Setup
- [x] Initialize Git repository
- [x] Create `.gitignore` excluding `media_entries.json`, raw CSVs, `preprocess.log`
- [x] Create `requirements.txt` with: `streamlit`, `requests`, `pydantic`, `pytest`, `spacy`
- [x] Write `setup.sh` to:
  - [x] Create Python virtual environment
  - [x] Install dependencies
  - [x] Export placeholders for `TMDB_API_KEY`, `IGDB_API_KEY`, `OPENLIBRARY_API_KEY`
- [x] Create `tests/test_setup.py` with a dummy test that always passes

## 2. CSV Loader & Year Propagation
- [x] Implement `load_weekly_records(path: str) -> List[Dict]` in `preprocess.py`
- [x] Parse `DateRange` into `start_date` and `end_date` (YYYY-MM-DD), inferring missing years
- [x] Return records with `start_date`, `end_date`, and `raw_notes`
- [x] Write tests in `tests/test_loader.py` for date parsing and year propagation

## 3. NLP Extraction Engine
- [x] Add `extract_entries(record: Dict) -> List[Dict]` in `preprocess.py`
- [x] Split `raw_notes` on `&` and newlines
- [x] Detect actions (`started`, `finished`, `watched`) using regex or spaCy
- [x] Return entries with `title`, `action`, and `date`
- [x] Write tests in `tests/test_media_extractor.py` covering various phrasings
- [ ] Handle titles with an "&" or "," in the name

## 4. API Tagger & Hints Support
- [x] Create `preprocessing/media_tagger.py`
- [x] Load `hints.yaml` for manual overrides
- [x] Implement stub functions: `query_tmdb`, `query_igdb`, `query_openlibrary`
- [x] Write `apply_tagging(entries: List[Dict]) -> List[Dict]`:
  - [x] Apply hints first, then API calls
  - [x] Attach `type`, `tags` (genre, platform, mood), and `confidence`
- [x] Write tests in `tests/test_media_tagger.py` with mocked API responses and hint overrides
- [x] Implement `query_tmdb`
- [x] Implement `query_igdb`
- [ ] Implement `query_openlibrary`
- [ ] Batch titles to minimize requests to the APIs
- [ ] Trim seasons
- [ ] Use hints to limit the DBs queried for a title

## 5. JSON Schema & Validation
- [ ] Define `MediaEntry` Pydantic model in `models.py`
- [ ] Validate entries in `preprocess.py` and serialize to `media_entries.json`
- [ ] Write tests in `tests/test_models.py` for model instantiation and JSON output

## 6. Streamlit Skeleton
- [ ] Create `app/streamlit_app.py`
- [ ] Load `media_entries.json`
- [ ] Display a header and JSON dump with `st.json()`
- [ ] Add a "Reload Data" button
- [ ] Write a smoke test in `tests/test_app.py`

## 7. Bar Layout & Fading Logic
- [ ] Compute continuous weekly axis using Pandas or dateutil
- [ ] Map entries to x-position (week index) and length (# of weeks)
- [ ] Calculate fade parameters for in-progress and lead-in entries
- [ ] Render bars via `st.plotly_chart` with a dark theme
- [ ] Write tests in `tests/test_layout.py` for positions, lengths, and opacities

## 8. Filters & Search
- [ ] Add Streamlit widgets:
  - [ ] Multi-select for `type`, `genre`, `platform`, `mood`
  - [ ] Text input for title search
- [ ] Implement filtering logic before rendering entries
- [ ] Write tests in `tests/test_filters.py`

## 9. Tooltips & Styling
- [ ] Implement hover tooltips showing:
  - Raw `Notes` text
  - Canonical title, dates, duration, and tags
- [ ] Apply dark CSS settings:
  - Slate background, subtle gridlines, accent colors
- [ ] Perform manual QA
- [ ] Add a snapshot test in `tests/test_ui_snapshot.py`

## 10. Integration & Documentation
- [ ] Write `scripts/run_all.sh` to:
  1. Run `preprocess.py` on a sample CSV
  2. Launch the Streamlit app
- [ ] Add `tests/test_integration.py`:
  - Programmatically call `preprocess.py`
  - Import and instantiate the Streamlit app
- [ ] Draft `README.md` with:
  - Project overview
  - Setup and usage instructions
  - Testing guide
- [ ] Tag version `v0.1.0` in Git

