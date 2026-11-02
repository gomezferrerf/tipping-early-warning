"""Smoke tests of the slide-deck helpers (run only where the ``deck`` extra is installed)."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest

from tipping.paths import project_root

pytest.importorskip("pptx", reason="the deck extra (python-pptx) is not installed")


def _load_deck_module(name: str) -> ModuleType:
    """Import ``deck/<name>.py`` (the deck directory is not a package)."""
    path = project_root() / "deck" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"deck_{name}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses and typing look the module up by name
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def test_fmt_es_uses_a_decimal_comma_and_never_rounds_up_to_one() -> None:
    fmt_es = _load_deck_module("build_deck").fmt_es
    assert fmt_es(0.5) == "0,50"
    assert fmt_es(0.9998) == "0,9998"
    assert fmt_es(1.0) == "1,00"


def test_the_talk_script_parses_into_notes_for_the_slides() -> None:
    export_notes = _load_deck_module("export_notes")
    text = (project_root() / "deck" / "guion.md").read_text(encoding="utf-8")
    notes = export_notes.parse_guion(text)
    assert len(notes) >= 15
    assert all(isinstance(value, str) and value for value in notes.values())
