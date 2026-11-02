"""Tests of the command-line interface."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from tipping import cli
from tipping.cli import app

runner = CliRunner()


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    commands = (
        "simulate",
        "sweep",
        "confound",
        "key-numbers",
        "figures",
        "animate",
        "deck",
        "reproduce",
    )
    for command in commands:
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
        (["confound"], "tipping.confound"),
        (["key-numbers"], "tipping.key_numbers"),
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


def test_reproduce_runs_every_step_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def stub(name: str) -> Callable[..., Any]:
        def run(*args: Any, **kwargs: Any) -> Any:
            calls.append(name + (":" + str(args[0]) if name in {"figures", "animate"} else ""))
            return [] if name in {"figures", "animate"} else (Path("a"), Path("b"))

        return run

    entries = {
        "tipping.sweep.run_sweep": "sweep",
        "tipping.confound.main": "confound",
        "tipping.key_numbers.main": "key-numbers",
        "tipping.viz.figures.make_all": "figures",
        "tipping.viz.animations.make_all": "animate",
    }

    def fake_load(module: str, attribute: str, command: str) -> Callable[..., Any]:
        return stub(entries[f"{module}.{attribute}"])

    monkeypatch.setattr(cli, "_load_entry", fake_load)
    result = runner.invoke(app, ["reproduce"])
    assert result.exit_code == 0, result.output
    assert calls == [
        "sweep",
        "confound",
        "key-numbers",
        "figures:es",
        "figures:en",
        "animate:es",
    ]


def test_deck_command_reports_a_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, package=None: None)
    result = runner.invoke(app, ["deck"])
    assert result.exit_code == 1
    assert "uv sync --extra deck" in result.output


def test_deck_command_reports_a_missing_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TIPPING_ROOT", str(tmp_path))
    result = runner.invoke(app, ["deck"])
    assert result.exit_code == 1
    assert "build_deck.py" in result.output


def test_deck_command_passes_the_repo_url_and_the_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "deck").mkdir()
    (tmp_path / "deck" / "build_deck.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("TIPPING_ROOT", str(tmp_path))
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, package=None: object())
    seen: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        assert kwargs["cwd"] == tmp_path.resolve()
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, ["deck", "--repo-url", "https://example.org/x"])
    assert result.exit_code == 3
    assert seen[0][1].endswith("build_deck.py")
    assert seen[0][2:] == ["--repo-url", "https://example.org/x"]
