"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tipping.config import ExperimentConfig, load_config
from tipping.paths import default_config_path


@pytest.fixture
def rng() -> np.random.Generator:
    """Return a seeded random generator."""
    return np.random.default_rng(12345)


@pytest.fixture(scope="session")
def default_config_file() -> Path:
    """Return the path of the baseline YAML configuration."""
    return default_config_path()


@pytest.fixture(scope="session")
def baseline(default_config_file: Path) -> ExperimentConfig:
    """Return the baseline experiment configuration."""
    return load_config(default_config_file)
