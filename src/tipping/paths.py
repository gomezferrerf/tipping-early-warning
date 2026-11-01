"""Filesystem locations used by the project.

All locations derive from the project root, which is resolved in this order:

1. the ``TIPPING_ROOT`` environment variable, if set;
2. the nearest ancestor of this file that contains ``pyproject.toml``;
3. the nearest ancestor of the current working directory that contains ``pyproject.toml``.

The functions are pure: they never create directories.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "TIPPING_ROOT"


def _find_upwards(start: Path) -> Path | None:
    """Return the nearest ancestor of ``start`` (inclusive) with a ``pyproject.toml``."""
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return None


def project_root() -> Path:
    """Locate the project root directory.

    Returns
    -------
    pathlib.Path
        Absolute path of the project root.

    Raises
    ------
    FileNotFoundError
        If ``TIPPING_ROOT`` is unset and no ``pyproject.toml`` can be found above this file
        or above the current working directory.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    found = _find_upwards(Path(__file__).resolve().parent) or _find_upwards(Path.cwd().resolve())
    if found is None:
        msg = f"Cannot locate the project root: set {ENV_VAR} or run inside the repository."
        raise FileNotFoundError(msg)
    return found


def results_dir() -> Path:
    """Return the directory for generated result tables (``<root>/results``)."""
    return project_root() / "results"


def assets_dir() -> Path:
    """Return the directory for generated figures and animations (``<root>/docs/assets``)."""
    return project_root() / "docs" / "assets"


def data_dir() -> Path:
    """Return the directory for intermediate data (``<root>/data``)."""
    return project_root() / "data"


def config_dir() -> Path:
    """Return the directory holding the YAML configurations (``<root>/configs``)."""
    return project_root() / "configs"


def default_config_path() -> Path:
    """Return the path of the baseline experiment configuration."""
    return config_dir() / "default.yaml"
