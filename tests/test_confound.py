"""Tests for the noise-amplitude confound experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tipping.config import IndicatorConfig, SimConfig
from tipping.confound import (
    FRAME_COLUMNS,
    POOLED_SEED,
    Group,
    build_scenarios,
    group_seed,
    group_stats,
    indicator_traces,
    main,
    run_confound,
    simulate_group,
    summarise_confound,
)
from tipping.evaluate import evaluate_pair
from tipping.simulate import derive_seeds

SIM = SimConfig(duration=800.0, n_runs=40, sigma=0.05)
IND = IndicatorConfig.for_sweep(800.0, SIM.sample_interval)
SEEDS = (1, 2)


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    """Small confound table (two seeds, sigma_end 0.15 and the null 0.05)."""
    return run_confound(seeds=SEEDS, sigma_ends=(0.05, 0.15), sim=SIM, indicators=IND, n_boot=30)


def _pooled(frame: pd.DataFrame, scenario: str, indicator: str) -> pd.Series:
    sel = frame[
        (frame["scenario"] == scenario)
        & (frame["indicator"] == indicator)
        & (frame["seed"] == POOLED_SEED)
    ]
    assert len(sel) == 1
    return sel.iloc[0]


def test_schema_and_row_count(frame: pd.DataFrame) -> None:
    """One row per scenario x (seeds + pooled) x indicator, with the documented columns."""
    assert tuple(frame.columns) == FRAME_COLUMNS
    n_scenarios = len(build_scenarios((0.05, 0.15)))
    assert len(frame) == n_scenarios * (len(SEEDS) + 1) * 2
    assert set(frame["indicator"]) == {"variance", "ar1"}
    assert set(frame["seed"]) == {*SEEDS, POOLED_SEED}
    finite = frame[["auc", "tpr", "auc_ci_lo", "auc_ci_hi"]]
    assert np.isfinite(finite.to_numpy()).all()
    assert (frame["auc_ci_lo"] <= frame["auc_ci_hi"]).all()
    assert ((frame["auc"] >= 0.0) & (frame["auc"] <= 1.0)).all()


def test_deterministic() -> None:
    """The table is a pure function of the seeds."""
    kwargs = {"seeds": (3,), "sigma_ends": (0.15,), "sim": SIM, "indicators": IND, "n_boot": 10}
    a = run_confound(**kwargs)  # type: ignore[arg-type]
    b = run_confound(**kwargs)  # type: ignore[arg-type]
    pd.testing.assert_frame_equal(a, b)


def test_null_scenario_auc_near_half(frame: pd.DataFrame) -> None:
    """noise_0.05 is statistically identical to the control: both AUCs are near 0.5."""
    for indicator in ("variance", "ar1"):
        row = _pooled(frame, "noise_0.05", indicator)
        assert abs(float(row["auc"]) - 0.5) < 0.15


def test_noise_ramp_flags_variance_more_than_ar1(frame: pd.DataFrame) -> None:
    """Noise tripling at constant r: variance separates (AUC ~ 1), AR(1) does not."""
    var = _pooled(frame, "noise_0.15", "variance")
    ar1 = _pooled(frame, "noise_0.15", "ar1")
    assert float(var["auc"]) > 0.95
    assert float(ar1["auc"]) < 0.8
    assert float(var["tpr"]) > float(ar1["tpr"])
    # the rolling variance grows by a large factor, the AR(1) barely moves
    assert float(var["change_pos"]) > 1.5
    assert abs(float(ar1["change_pos"])) < 0.1


def test_fold_flags_both_indicators(frame: pd.DataFrame) -> None:
    """Positive control: both indicators separate the approach to the fold from the control."""
    assert float(_pooled(frame, "fold", "variance")["auc"]) > 0.9
    assert float(_pooled(frame, "fold", "ar1")["auc"]) > 0.9


def test_fold_scenario_matches_evaluate_pair() -> None:
    """The fold scenario uses the same code path as the baseline evaluation."""
    fold, control = Group("fold", -0.6, None), Group("control", 0.0, None)
    ramp = simulate_group(SIM, fold, 5)
    null = simulate_group(SIM, control, 5)
    res = evaluate_pair(ramp, null, IND)
    pos, neg = group_stats(ramp, IND), group_stats(null, IND)
    assert np.allclose(res.tau_ramp_var, pos.tau_var[pos.valid])
    assert np.allclose(res.tau_null_ar1, neg.tau_ar1[neg.valid])
    assert pos.n_tipped_early == round(res.frac_ramp_tipped_early * pos.n_runs)
    assert neg.n_tipped_ever == round(res.frac_null_tipped * neg.n_runs)


def test_control_seed_matches_run_experiment() -> None:
    """The control group has the null seed of run_experiment; others depend on the name only."""
    assert group_seed(7, Group("control", 0.0, None)) == derive_seeds(7)[1]
    a = group_seed(7, Group("noise_0.10", 0.0, 0.10))
    assert a == group_seed(7, Group("noise_0.10", 0.0, 0.10))
    assert a != group_seed(7, Group("noise_0.15", 0.0, 0.15))
    assert a != group_seed(8, Group("noise_0.10", 0.0, 0.10))


def test_constant_r_group_has_flat_deterministic_schedule() -> None:
    """r_end = 0 gives a constant schedule (no workaround of the Ramp class is needed)."""
    traj = simulate_group(SIM, Group("noise_0.10", 0.0, 0.10), 1)
    assert np.all(traj.r == 0.0)
    assert traj.sigma_end == 0.10


def test_main_writes_parquet_and_json(tmp_path: Path) -> None:
    """main() writes both artefacts with the keys the deck build reads."""
    parquet_path, json_path = main(tmp_path, n_runs=20, seeds=(1,), sigma_ends=(0.15,), n_boot=10)
    assert parquet_path.is_file()
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(summary) == {"config", "glossary", "scenarios"}
    assert set(summary["scenarios"]) == {"fold", "noise_0.15", "mixed_0.15", "mixed_vs_noise_0.15"}
    entry = summary["scenarios"]["noise_0.15"]["pooled"]["variance"]
    assert {"auc", "auc_ci95", "tpr_at_5pct_fpr", "tpr_ci95", "median_tau_pos"} <= set(entry)
    assert summary["config"]["seeds"] == [1]


def test_summary_is_json_serialisable(frame: pd.DataFrame) -> None:
    """The summary round-trips through json (NaN replaced by None upstream)."""
    summary = summarise_confound(frame, SIM, IND, 30)
    assert summary["scenarios"]["noise_0.15"]["sigma_at_analysis_end"] == pytest.approx(
        0.05 + 0.10 * IND.analysis_fraction
    )


def test_indicator_traces_shapes() -> None:
    """Percentile bands share the time axis and are ordered."""
    tr = indicator_traces(0.15, n_runs=10, seed=1)
    for band in (tr.variance_noise, tr.ar1_noise, tr.variance_control, tr.ar1_control):
        assert band.shape == (3, tr.t.size)
        assert np.all(band[0] <= band[1] + 1e-12)
        assert np.all(band[1] <= band[2] + 1e-12)
