"""Tests of the command-line interface."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest
from typer.testing import CliRunner

from tipping.cli import app

runner = CliRunner()


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("simulate", "sweep", "figures", "animate", "reproduce"):
        assert command in result.output


def test_simulate_prints_summary_table() -> None:
    result = runner.invoke(app, ["simulate", "--seed", "3", "--n-runs", "30", "--duration", "400"])
    assert result.exit_code == 0, result.output
    for text in ("AUC", "TPR @ 5% FPR", "median tau", "tipped", "seed 3"):
        assert text in result.output


@pytest.mark.parametrize(
    ("args", "module"),
    [
        (["sweep"], "tipping.sweep"),
        (["figures", "--lang", "es"], "tipping.viz.figures"),
        (["animate", "--lang", "en"], "tipping.viz.animations"),
        (["reproduce"], "tipping.sweep"),
    ],
)
def test_missing_modules_give_a_friendly_error(
    args: list[str], module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> ModuleType:
        if name == module:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert module in result.output
    assert "Traceback" not in result.output


def test_unrelated_import_errors_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> ModuleType:
        if name == "tipping.sweep":
            raise ModuleNotFoundError(
                "No module named 'nonexistent_dependency'", name="nonexistent_dependency"
            )
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    result = runner.invoke(app, ["sweep"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ModuleNotFoundError)


def test_invalid_language_is_rejected() -> None:
    result = runner.invoke(app, ["figures", "--lang", "fr"])
    assert result.exit_code == 2
