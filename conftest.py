"""Shared pytest fixtures for endure-plan-engine."""

import json
import pytest
from pathlib import Path


BASE_DIR = Path(__file__).parent


@pytest.fixture
def base_dir():
    return BASE_DIR


@pytest.fixture
def sarah_intake():
    fixture_path = BASE_DIR / "tests" / "fixtures" / "sarah_printz.json"
    with open(fixture_path) as f:
        return json.load(f)
