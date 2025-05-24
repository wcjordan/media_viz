"""Unit tests for loading the hints file."""

from unittest.mock import patch, mock_open

import pytest
import yaml

from preprocessing import utils
from preprocessing.utils import load_hints


@pytest.fixture(autouse=True)
def reset_hints_cache():
    """Reset hints cache before each test to ensure consistent state."""
    utils.hints_cache = {}
    yield


def test_load_hints_success(sample_hints):
    """Test loading hints from a YAML file successfully."""
    mock_yaml_content = yaml.dump(sample_hints)

    with patch("builtins.open", mock_open(read_data=mock_yaml_content)), patch(
        "os.path.exists", return_value=True
    ):
        hints = load_hints("fake_path.yaml")

    assert hints == sample_hints
    assert "FF7" in hints
    assert hints["FF7"]["canonical_title"] == "Final Fantasy VII Remake"


def test_load_hints_file_not_found():
    """Test handling when hints file is not found."""
    with patch("os.path.exists", return_value=False):
        hints = load_hints("nonexistent_file.yaml")

    assert hints == {}


def test_load_hints_invalid_yaml():
    """Test handling invalid YAML content."""
    invalid_yaml = "invalid: yaml: content: - ["

    with patch("builtins.open", mock_open(read_data=invalid_yaml)), patch(
        "os.path.exists", return_value=True
    ):
        hints = load_hints("invalid.yaml")

    assert hints == {}
