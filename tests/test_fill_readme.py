"""Tests of the helper that fills the README results block."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest

from tipping.paths import project_root


def _load_script() -> ModuleType:
    path = project_root() / "scripts" / "fill_readme.py"
    spec = importlib.util.spec_from_file_location("fill_readme_script", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (0.5, 2, "0.50"),
        (0.9998, 2, "0.99"),  # never rounded up to 1.00
        (0.9998, 4, "0.9998"),
        (1.0, 2, "1.00"),
        (-0.001, 2, "0.00"),  # no negative zero
        (-0.76, 2, "-0.76"),
    ],
)
def test_num_never_rounds_up_to_one(value: float, digits: int, expected: str) -> None:
    assert _load_script().num(value, digits) == expected


def test_replace_block_keeps_the_markers_and_is_idempotent() -> None:
    script = _load_script()
    readme = f"before\n{script.START}\nold\n{script.END}\nafter\n"
    once = script.replace_block(readme, "new text")
    assert once == f"before\n{script.START}\nnew text\n{script.END}\nafter\n"
    assert script.replace_block(once, "new text") == once
