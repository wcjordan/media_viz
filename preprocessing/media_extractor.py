"""
Preprocessing stage to extract media entries from the Notes column of a weekly record.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

SINGLE_EVENT_VERBS = ("played", "read", "watched", "explored")
RANGE_VERBS = ("finished", "started")
CONTINUATION_VERB = "&"
IGNORED_VERBS = (
    "celebrated",
    "got",
    "home",
    "hooked",
    "i",
    "installed",
    "looked",
    "put",
    "reviewed",
    "setup",
    "spoke",
    "we",
)
VERB_MAPPING = {
    "finshed": "finished",
    "gave up": "finished",
    "good progress on": "started",
    "restarted": "started",
    "resumed": "started",
}
ALL_VERBS = (
    SINGLE_EVENT_VERBS
    + RANGE_VERBS
    + IGNORED_VERBS
    + tuple(VERB_MAPPING.keys())
    + tuple(
        CONTINUATION_VERB,
    )
)


def extract_entries(record: Dict) -> List[Dict]:
    """
    Extract media entries from a weekly record's raw notes.

    Args:
        record: Dictionary containing start_date, end_date, and raw_notes

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

    # Split the raw notes on newlines to process each line separately
    last_action = None
    for line in raw_notes.splitlines():
        line = line.strip()
        new_entries, last_action = _extract_entries_from_line(
            line, start_date, last_action
        )
        entries.extend(new_entries)

    logger.info(
        "Extracted %d entries from record with dates %s to %s",
        len(entries),
        start_date,
        end_date,
    )
    return entries


def _extract_entries_from_line(
    line: str, start_date: str, last_action: str = None
) -> List[Dict]:
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
    Returns:
        entries: A list of dictionaries representing a media entry with the
                 following keys:
                    - "action": The action performed (e.g., "finished", "started").
                    - "title": The title of the media item.
                    - "date": The start date of the week.
        action: The action from the current line, which may be used for the next line.
    """
    entries = []

    # Split the line to extract the action from the items
    action = None
    for verb in ALL_VERBS:
        if line.lower().startswith(f"{verb} "):
            action_len = len(verb) + 1
            titles_str = line[action_len:].strip()
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
        if action not in IGNORED_VERBS or start_date > "2025":
            logger.warning("Skipping line with invalid action '%s': %s", action, line)
        return entries, action

    # Split the entities on '&' or newlines
    for title in titles_str.split(CONTINUATION_VERB):
        title = title.strip()
        if title:
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
