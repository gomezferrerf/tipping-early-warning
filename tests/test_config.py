"""Tests of the configuration models, YAML loading and path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tipping import paths
from tipping.config import (
    ExperimentConfig,
    IndicatorConfig,
    SimConfig,
    SweepConfig,
    load_config,
    load_sweep_config,
)
from tipping.model import FOLD_R


def test_default_yaml_is_the_baseline(baseline: ExperimentConfig) -> None:
    sim, ind = baseline.sim, baseline.indicators
    assert (sim.dt, sim.sample_every, sim.sigma, sim.x0) == (0.01, 50, 0.05, 1.0)
    assert (sim.r_start, sim.r_end, sim.duration, sim.n_runs) == (0.0, -0.6, 2000.0, 300)
    assert sim.seed == 42
    assert sim.sample_interval == pytest.approx(0.5)
    assert (ind.window, ind.detrend_window) == (400, 100)
    assert (ind.analysis_fraction, ind.min_points, ind.fpr) == (0.6, 15, 0.05)
    assert ind.resolved_step() == 10
    assert baseline == ExperimentConfig()  # the YAML restates the code defaults


def test_ramp_control_and_fold_time(baseline: ExperimentConfig) -> None:
    sim = baseline.sim
    assert sim.ramp().r_at(sim.duration) == pytest.approx(-0.6)
    assert sim.control().r_at(sim.duration / 2) == 0.0
    fold_time = sim.fold_time()
    assert fold_time == pytest.approx(2000 * FOLD_R / 0.6)
    assert fold_time == pytest.approx(1283, abs=1)
    assert sim.model_copy(update={"r_end": -0.2}).fold_time() is None


def test_validation_errors() -> None:
    with pytest.raises(ValidationError):
        SimConfig(sigma=-0.1)
    with pytest.raises(ValidationError):
        SimConfig(n_runs=0)
    with pytest.raises(ValidationError, match="duration"):
        SimConfig(duration=0.1)
    with pytest.raises(ValidationError):
        IndicatorConfig(analysis_fraction=1.5)
    with pytest.raises(ValidationError, match="Extra"):
        SimConfig(sigmaa=0.1)  # type: ignore[call-arg]


def test_models_are_frozen() -> None:
    with pytest.raises(ValidationError):
        SimConfig().sigma = 1.0


def test_sweep_window_rule() -> None:
    # W = max(10, round(0.10 * duration / interval)); detrend = max(5, W // 4).
    long = IndicatorConfig.for_sweep(2000.0, 0.5)
    assert (long.window, long.detrend_window) == (400, 100)
    short = IndicatorConfig.for_sweep(100.0, 0.5)
    assert (short.window, short.detrend_window) == (20, 5)
    tiny = IndicatorConfig.for_sweep(20.0, 0.5)
    assert (tiny.window, tiny.detrend_window) == (10, 5)
    assert IndicatorConfig.for_sweep(400.0, 0.5, fpr=0.1).fpr == 0.1
    assert IndicatorConfig(window=20).resolved_step() == 1
    assert IndicatorConfig(window=20, tau_step=3).resolved_step() == 3


def test_load_config_overrides_and_rejects_typos(tmp_path: Path) -> None:
    good = tmp_path / "cfg.yaml"
    good.write_text("sim:\n  sigma: 0.1\n  n_runs: 5\n", encoding="utf-8")
    cfg = load_config(good)
    assert cfg.sim.sigma == 0.1
    assert cfg.sim.n_runs == 5
    assert cfg.sim.dt == 0.01  # untouched default
    bad = tmp_path / "bad.yaml"
    bad.write_text("sim:\n  sigmaa: 0.1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(bad)
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    assert load_config(empty) == ExperimentConfig()
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("42\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_config(scalar)


def test_sweep_config_defaults_and_loading(tmp_path: Path) -> None:
    cfg = SweepConfig()
    assert cfg.sigmas == [0.03, 0.05, 0.10, 0.15, 0.30]
    assert cfg.durations == [100, 200, 400, 1000, 2000]
    assert cfg.seeds == [1, 2, 3]
    assert cfg.n_runs == 300
    sim = cfg.sim_config(0.15, 400.0, 2)
    assert (sim.sigma, sim.duration, sim.seed, sim.n_runs) == (0.15, 400.0, 2, 300)
    ind = cfg.indicator_config(400.0)
    assert (ind.window, ind.detrend_window) == (80, 20)
    flat = tmp_path / "flat.yaml"
    flat.write_text("sigmas: [0.05]\ndurations: [100]\nseeds: [7]\n", encoding="utf-8")
    assert load_sweep_config(flat).seeds == [7]
    nested = tmp_path / "nested.yaml"
    nested.write_text("sweep:\n  n_runs: 12\n", encoding="utf-8")
    assert load_sweep_config(nested).n_runs == 12


def test_paths_env_override_and_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    root = paths.project_root()
    assert (root / "pyproject.toml").is_file()
    assert paths.default_config_path() == root / "configs" / "default.yaml"
    assert paths.default_config_path().is_file()
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    assert paths.project_root() == tmp_path.resolve()
    assert paths.results_dir() == tmp_path.resolve() / "results"
    assert paths.assets_dir() == tmp_path.resolve() / "docs" / "assets"
    assert paths.data_dir() == tmp_path.resolve() / "data"
    assert not (tmp_path / "results").exists()  # pure: nothing is created
