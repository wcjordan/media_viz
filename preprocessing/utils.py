"""
Shared utility functions for preprocessing modules.
"""

import logging
import os
from typing import Dict, Optional
import yaml

logger = logging.getLogger(__name__)
DEFAULT_HINTS_PATH = os.path.join(os.path.dirname(__file__), "hints.yaml")


def load_hints(hints_path: Optional[str] = None) -> Dict:
    """
    Load hints from a YAML file for manual overrides.

    Args:
        hints_path: Path to the hints YAML file. If None, uses default path.

    Returns:
        Dictionary containing hints for media entries.
    """
    if hints_path is None:
        hints_path = DEFAULT_HINTS_PATH

    if not os.path.exists(hints_path):
        logger.warning(
            "Hints file not found at %s. No manual overrides will be applied.",
            hints_path,
        )
        return {}

    try:
        with open(hints_path, "r", encoding="utf-8") as file:
            hints = yaml.safe_load(file)
            if not hints:
                return {}
            logger.info("Loaded %d hints from %s", len(hints), hints_path)
            return hints
    except (yaml.YAMLError, IOError, FileNotFoundError) as e:
        logger.warning("Failed to load hints file: %s", e)
        return {}
