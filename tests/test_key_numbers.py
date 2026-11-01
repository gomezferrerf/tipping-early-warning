"""Tests of the helpers that compute the numbers quoted in the talk (tiny configurations)."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tipping import key_numbers as kn
from tipping.config import ExperimentConfig, IndicatorConfig, SimConfig
from tipping.evaluate import run_experiment
from tipping.model import FOLD_R, growth_rate, upper_branch

TOP_LEVEL_KEYS = {
    "baseline",
    "sweep_summary",
    "model",
    "protocol",
    "horizon",
    "tipping_vs_fold",
    "window_vs_duration",
    "a2_illustration",
    "adiabaticity",
    "sweep_paired",
    "survivors",
    "detrend_control",
}


@pytest.fixture(scope="module")
def tiny() -> ExperimentConfig:
    """A short ramp that crosses the fold, with few runs."""
    return ExperimentConfig(
        sim=SimConfig(duration=200.0, n_runs=20, seed=7),
        indicators=IndicatorConfig(window=40, detrend_window=10, min_points=5),
    )


@pytest.fixture(scope="module")
def tiny_exp(tiny: ExperimentConfig) -> Any:
    """The tiny baseline experiment."""
    return run_experiment(tiny.sim, tiny.indicators)


def _sweep_frame() -> pd.DataFrame:
    rows = []
    for seed, (var_a, ar_a) in enumerate([(0.9, 0.8), (0.9, 0.8), (0.9, 0.8)]):
        rows.append((0.05, 100.0, seed, var_a, ar_a, 0.5, 0.4))
    for seed, (var_b, ar_b) in enumerate([(0.7, 0.6), (0.6, 0.7), (0.7, 0.6)]):
        rows.append((0.30, 100.0, seed, var_b, ar_b, 0.2, 0.3))
    return pd.DataFrame(
        rows, columns=["sigma", "duration", "seed", "auc_var", "auc_ar1", "tpr_var", "tpr_ar1"]
    )


def _summary_frame() -> pd.DataFrame:
    rows = [
        (0.15, 100.0, 300.0, 300.0, 0.2, 0.0, 0.6, 0.55),
        (0.30, 100.0, 282.5, 293.5, 0.9, 0.1, 0.56, 0.53),
        (0.30, 200.0, 274.0, 291.0, 0.98, 0.2, 0.6, 0.59),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "sigma",
            "duration",
            "n_valid_ramp",
            "n_valid_null",
            "frac_ramp_tipped_early",
            "frac_null_tipped",
            "auc_var_mean",
            "auc_ar1_mean",
        ],
    )


def test_model_constants() -> None:
    out = kn.model_constants()
    assert out["jump"] == pytest.approx(math.sqrt(3.0))
    assert out["loop_width"] == pytest.approx(2.0 * FOLD_R)
    assert out["lower_branch_at_fold"] == pytest.approx(-2.0 / math.sqrt(3.0))


def test_protocol_matches_config(tiny: ExperimentConfig) -> None:
    out = kn.protocol(tiny)
    assert out["window_time"] == pytest.approx(40 * 0.5)
    assert out["analysis_end_time"] == pytest.approx(0.6 * 200.0)
    assert out["analysis_end_r"] == pytest.approx(-0.36)
    assert out["ramp_rate"] == pytest.approx(0.6 / 200.0)


def test_horizon_rows(tiny: ExperimentConfig, tiny_exp: Any) -> None:
    out = kn.horizon_dependence(tiny, tiny_exp, fractions=(0.4, 0.6))
    assert [row["analysis_fraction"] for row in out["rows"]] == [0.4, 0.6]
    first, second = out["rows"]
    assert first["t_end"] < second["t_end"]
    assert first["time_before_fold"] > second["time_before_fold"]
    assert out["fold_fraction_of_ramp"] == pytest.approx(FOLD_R / 0.6, abs=0.01)


def test_escape_barrier_matches_normal_form() -> None:
    mu = 1e-4
    expected = (4.0 / 3.0) * 3.0 ** (-0.25) * mu**1.5
    assert kn.escape_barrier(-FOLD_R + mu) == pytest.approx(expected, rel=0.05)
    assert kn.escape_barrier(-FOLD_R + 0.1) > kn.escape_barrier(-FOLD_R + 0.01) > 0.0


def test_tipping_vs_fold_schema(tiny: ExperimentConfig, tiny_exp: Any) -> None:
    out = kn.tipping_vs_fold(tiny, tiny_exp, sigmas=(0.05, 0.15), lead_times=(5.0,))
    assert [row["sigma"] for row in out["by_sigma"]] == [0.05, 0.15]
    for row in out["by_sigma"]:
        assert 0.0 <= row["frac_tip_before_fold"] <= row["frac_tipped_ever"] <= 1.0
    assert 0.0 <= out["baseline"]["frac_tip_before_fold"] <= 1.0
    (barrier,) = out["barrier"]
    assert barrier["barrier"] > 0.0
    assert barrier["noise_energy"] == pytest.approx(tiny.sim.sigma**2 / 2.0)
    # more noise tips earlier (same ramp, same seed)
    assert out["by_sigma"][1]["median_tip_time"] <= out["by_sigma"][0]["median_tip_time"]


def test_window_vs_duration_smoke(tiny: ExperimentConfig) -> None:
    out = kn.window_vs_duration(tiny, ((200.0, 40, 10), (100.0, 20, 5)), seed=3, n_runs=15)
    assert [row["duration"] for row in out["rows"]] == [200.0, 100.0]
    assert out["rows"][1]["window_time"] == pytest.approx(10.0)
    for row in out["rows"]:
        for key in ("auc_var", "auc_ar1"):
            assert row[key] is None or 0.0 <= row[key] <= 1.0


def test_a2_illustration_reads_animation_constants(tiny: ExperimentConfig) -> None:
    from tipping.viz import animations

    out = kn.a2_illustration(tiny, n_seeds=4)
    assert out["sigma"] == animations.A2_SIGMA
    assert out["seed"] == animations.A2_SEED
    assert out["r_end"] == animations.A2_R_END
    assert out["sigma_ratio_vs_baseline"] == pytest.approx(animations.A2_SIGMA / 0.05)
    assert out["selected_min_x"] > animations.A2_MIN_X
    for key in ("at_animation_sigma", "at_baseline_sigma"):
        assert 0.0 <= out[key]["frac_tip"] <= out[key]["frac_dip_below_0p2"] <= 1.0


def test_adiabaticity_short_ramp_is_less_adiabatic(tiny: ExperimentConfig) -> None:
    out = kn.adiabaticity(tiny, durations=(100.0, 2000.0))
    short, long = out["rows"]
    assert short["ratio_relaxation_to_time_left"] > long["ratio_relaxation_to_time_left"]
    assert short["relaxation_time"] == pytest.approx(1.0 / abs(growth_rate(upper_branch(-0.36))))
    assert out["relaxation_time_r0"] == pytest.approx(0.5)


def test_breakdown_lead_time_solves_the_equation() -> None:
    rate = 0.0003
    lead = kn._breakdown_lead_time(rate)
    r = -FOLD_R + rate * lead
    assert 1.0 / abs(growth_rate(upper_branch(r))) == pytest.approx(lead, rel=1e-6)


def test_sweep_paired_counts() -> None:
    out = kn.sweep_paired(_sweep_frame())
    assert out["n_cells"] == 2
    assert out["auc_variance_wins"] == {"all_seeds": 1, "some_seeds": 1, "no_seed": 0}
    (exception,) = out["auc_exceptions"]
    assert (exception["sigma"], exception["seeds_variance_wins"]) == (0.30, 2)
    assert out["tpr_variance_wins"] == {"all_seeds": 1, "some_seeds": 0, "no_seed": 1}


def test_survivors_rows() -> None:
    out = kn.survivors(_summary_frame())
    assert [(row["sigma"], row["duration"]) for row in out["rows"]] == [
        (0.15, 100.0),
        (0.30, 100.0),
        (0.30, 200.0),
    ]
    assert out["rows"][1]["n_valid_ramp"] == pytest.approx(282.5)


def test_detrend_control_smoke(tiny: ExperimentConfig) -> None:
    out = kn.detrend_control(tiny, n_runs=15)
    assert out["mean_start"] == pytest.approx(1.0)
    assert out["mean_at_analysis_end"] < out["mean_start"]
    for key in ("variance", "ar1"):
        assert out[key]["auc"] is None or 0.0 <= out[key]["auc"] <= 1.0


def test_jsonable_maps_nan_and_numpy() -> None:
    cleaned = kn._jsonable(
        {"a": np.float64(1.5), "b": [float("nan"), np.int64(2)], "c": np.arange(2)}
    )
    assert cleaned == {"a": 1.5, "b": [None, 2], "c": [0, 1]}
    json.dumps(cleaned, allow_nan=False)


def test_compute_key_numbers_schema_and_json(tiny: ExperimentConfig) -> None:
    data = kn.compute_key_numbers(
        tiny,
        _sweep_frame(),
        _summary_frame(),
        a2_seeds=3,
        window_runs=12,
        window_settings=((200.0, 40, 10),),
        adiabaticity_durations=(100.0,),
    )
    assert set(data) == TOP_LEVEL_KEYS
    assert set(data["horizon"]["rows"][0]) >= {"auc_var", "auc_ar1", "tpr_var", "tpr_ar1"}
    assert set(data["tipping_vs_fold"]) >= {"baseline", "by_sigma", "deterministic_tip_time"}
    json.dumps(data, allow_nan=False)
