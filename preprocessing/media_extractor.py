"""
Preprocessing stage to extract media entries from the Notes column of a weekly record.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from preprocessing.utils import load_hints

logger = logging.getLogger(__name__)

SINGLE_EVENT_VERBS = ("played", "read", "watched", "explored")
RANGE_VERBS = ("finished", "started")
CONTINUATION_VERB = "&"
IGNORED_ENTRIES = (
    "Celebrated Cole's first BDay!",
    "Finished migrating Chalk to the new GCP project",
    "Got mobile auth POC working for Chalk",
    "Got Test-Sheriff running in k8s",
    "Home inspection & attorney review went well for the house!",
    "Hooked up PS remote play",
    "I wrote a very large check... as earnest money for the house",
    "Looked into Sentry integrations",
    "Put an offer in on a house!",
    "Resumed working out & Chalk",
    "Reviewed Westworld s3",
    "Setup gaming desktop",
    "Spoke w/ NJ realtor & got mortgage pre-approval.  Exploring securities backed lending.",
    "Started considering Fatherhood & Mindfulness habits more like Recreation",
    "Started learning Terraform",
    "Started materials science course",
    "Started researching ML training on GPU & Terraform",
    "We moved to Livingston!",
)
VERB_MAPPING = {
    "finshed": "finished",
    "finished playing": "finished",
    "finished reading": "started",
    "finished watching": "started",
    "gave up on": "finished",
    "good progress on": "started",
    "installed": "started",
    "restarted": "started",
    "resumed": "started",
    "started & finished": SINGLE_EVENT_VERBS[0],
    "started listening to": "started",
    "started playing": "started",
    "started reading": "started",
    "started watching": "started",
}
ALL_VERBS = (
    tuple(VERB_MAPPING.keys())
    + SINGLE_EVENT_VERBS
    + RANGE_VERBS
    + IGNORED_ENTRIES
    + tuple(
        CONTINUATION_VERB,
    )
)




def extract_entries(record: Dict, hints_path: Optional[str] = None) -> List[Dict]:
    """
    Extract media entries from a weekly record's raw notes.

    Args:
        record: Dictionary containing start_date, end_date, and raw_notes
        hints_path: Optional path to the hints YAML file

    Returns:
        List of dictionaries with title, action, and date
    """
    entries = []

    # Get the raw notes and dates from the record
    raw_notes = record.get("raw_notes", "")
    start_date = record.get("start_date")
    end_date = record.get("end_date")

    if not start_date or not end_date:
        logger.warning("Skipping record with missing data: %s", record)
        return entries

    # Load hints to avoid splitting titles that contain & or ,
    hints = load_hints(hints_path)
    
    # Get all hint titles and aliases that might contain & or ,
    protected_titles = []
    for key, hint_data in hints.items():
        if '&' in key or ',' in key:
            protected_titles.append(key)
        
        canonical_title = hint_data.get('canonical_title', '')
        if canonical_title and ('&' in canonical_title or ',' in canonical_title):
            protected_titles.append(canonical_title)

    # Split the raw notes on newlines to process each line separately
    last_action = None
    for line in raw_notes.splitlines():
        line = line.strip()
        new_entries, last_action = _extract_entries_from_line(
            line, start_date, last_action, protected_titles
        )
        entries.extend(new_entries)

    logger.info(
        "Extracted %d entries from record with dates %s to %s",
        len(entries),
        start_date,
        end_date,
    )
    return entries


def _get_entries(title: str, action: str, start_date: str) -> List[Dict]:
    """
    Generate a list of entries based on the title, action, and start date.

    Args:
        title: The title of the media item.
        action: The action performed (e.g., "finished", "started").
        start_date: The start date of the week.

    Returns:
        entries: A list of dictionaries where each entry represents a media entry with the
                 following keys:
                    - "action": The action performed (e.g., "finished", "started").
                    - "title": The title of the media item.
                    - "date": The start date of the week.
    """
    entries = []
    if action in RANGE_VERBS:
        entry = {
            "action": action,
            "title": title,
            "date": start_date,
        }
        entries.append(entry)
    else:
        for sub_action in RANGE_VERBS:
            entry = {
                "action": sub_action,
                "title": title,
                "date": start_date,
            }
            entries.append(entry)
    return entries


def _extract_entries_from_line(
    line: str, start_date: str, last_action: str = None, protected_titles: List[str] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Extract media entries from a single line of a weekly record's raw notes.

    This helper method processes a single line of the Notes column, identifies the action
    (e.g., "finished", "started"), and splits the entities on the '&' character to generate
    individual entries. Each entry includes the action, title, and the provided start date.

    Args:
        line: A string containing a single line from the Notes column. The line is expected
              to start with an action followed by one or more titles separated by '&'.
        start_date: A string representing the start date of the week, used as the date for
                    all generated entries.
        last_action: The action from the previous line, if any.
                     This is used to handle cases where the action is not explicitly stated in the line.
        protected_titles: List of titles from hints.yaml that should not be split.
    Returns:
        Returns a Tuple of entries list and action string
            - entries: A list of dictionaries representing a media entry with the
                       following keys:
                        - "action": The action performed (e.g., "finished", "started").
                        - "title": The title of the media item.
                        - "date": The start date of the week.
            - action: The action from the current line, which may be used for the next line.
    """
    entries = []
    if line in IGNORED_ENTRIES:
        return entries, last_action

    # Split the line to extract the action from the items
    action = None
    for verb in ALL_VERBS:
        if line.lower().startswith(f"{verb.lower()} "):
            action_len = len(verb) + 1
            titles_str = line[action_len:].strip()

            # Entries before 2025 have already been checked and added to IGNORED_ENTRIES where necessary
            if (
                titles_str
                and titles_str[0].isalpha()
                and titles_str[0] == titles_str.lower()[0]
                and start_date > "2025"
            ):
                logger.warning(
                    "Title not capitalized.  This may indicate we missed part of the verb: %s",
                    line,
                )

            action = verb.lower()
            break

    if action is None:
        logger.warning("Skipping line with unknown action: %s", line)
        return entries, last_action

    if action == CONTINUATION_VERB:
        action = last_action

    # Normalize the action to handle typos or variations
    if action in VERB_MAPPING:
        action = VERB_MAPPING.get(action)

    if action not in RANGE_VERBS and action not in SINGLE_EVENT_VERBS:
        logger.warning("Skipping line with invalid action '%s': %s", action, line)
        return entries, action

    # Check if titles_str contains any protected titles
    if protected_titles:
        # Replace protected titles with placeholders to avoid splitting them
        placeholders = {}
        modified_titles_str = titles_str
        
        for i, protected_title in enumerate(protected_titles):
            if protected_title in titles_str:
                placeholder = f"__PROTECTED_TITLE_{i}__"
                modified_titles_str = modified_titles_str.replace(protected_title, placeholder)
                placeholders[placeholder] = protected_title
        
        # If we made replacements, use the modified string
        if placeholders:
            # Split on & or , that are not in protected titles
            split_titles = []
            for part in re.split("&|,", modified_titles_str):
                part = part.strip()
                # Restore any protected titles
                for placeholder, original in placeholders.items():
                    if placeholder in part:
                        part = part.replace(placeholder, original)
                if part:
                    split_titles.append(part)
            
            # Process each title
            for title in split_titles:
                if title:
                    entries.extend(_get_entries(title, action, start_date))
            return entries, action
    
    # If no protected titles or no matches, use the original splitting logic
    for title in re.split("&|,", titles_str):
        title = title.strip()
        if title:
            entries.extend(_get_entries(title, action, start_date))
    return entries, action


if __name__ == "__main__":
    # Example usage
    curr_entries = extract_entries(
        {
            "start_date": "2023-01-01",
            "end_date": "2023-01-07",
            "raw_notes": "Started The Hobbit",
        }
    )
    print(f"Extracted {curr_entries}")
