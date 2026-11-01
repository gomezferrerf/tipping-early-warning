"""Tests of the evaluation metrics and the ramp-versus-control comparison."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from tipping.config import ExperimentConfig, IndicatorConfig
from tipping.evaluate import (
    auc,
    bootstrap_ci,
    bootstrap_mean_ci,
    evaluate_pair,
    run_experiment,
    run_taus,
    tpr_at_fpr,
)
from tipping.simulate import Trajectories

FloatArray = NDArray[np.float64]


def _brute_force_auc(pos: FloatArray, neg: FloatArray) -> float:
    greater = (pos[:, None] > neg[None, :]).mean()
    ties = (pos[:, None] == neg[None, :]).mean()
    return float(greater + 0.5 * ties)


def test_auc_separable_identical_and_reversed() -> None:
    low, high = np.arange(10.0), np.arange(10.0) + 100.0
    assert auc(high, low) == 1.0
    assert auc(low, high) == 0.0
    assert auc(low, low) == pytest.approx(0.5)
    assert auc(np.array([1.0, 1.0]), np.array([1.0, 1.0, 1.0])) == pytest.approx(0.5)


def test_auc_matches_brute_force_with_ties(rng: np.random.Generator) -> None:
    pos = rng.integers(0, 8, size=40).astype(float)
    neg = rng.integers(0, 8, size=55).astype(float)
    assert auc(pos, neg) == pytest.approx(_brute_force_auc(pos, neg))


def test_auc_ignores_nonfinite_and_rejects_empty() -> None:
    assert auc(np.array([2.0, np.nan]), np.array([1.0, np.inf])) == 1.0
    with pytest.raises(ValueError, match="finite"):
        auc(np.array([np.nan]), np.array([1.0]))


def test_tpr_at_fpr() -> None:
    neg = np.arange(100.0)  # 95th percentile = 94.05
    threshold = float(np.quantile(neg, 0.95))
    pos = np.array([50.0, 94.0, 95.0, 99.0])
    assert tpr_at_fpr(pos, neg) == pytest.approx(np.mean(pos > threshold))
    assert tpr_at_fpr(pos, neg) == 0.5
    assert tpr_at_fpr(neg + 1000.0, neg) == 1.0
    assert tpr_at_fpr(neg - 1000.0, neg) == 0.0
    # Larger tolerated FPR cannot lower the TPR.
    assert tpr_at_fpr(pos, neg, fpr=0.5) >= tpr_at_fpr(pos, neg, fpr=0.05)
    with pytest.raises(ValueError, match="fpr"):
        tpr_at_fpr(pos, neg, fpr=1.5)


def test_bootstrap_ci_contains_point_estimate_and_is_seeded(rng: np.random.Generator) -> None:
    pos = rng.normal(0.8, 1.0, 80)
    neg = rng.normal(0.0, 1.0, 80)
    point = auc(pos, neg)
    lo, hi = bootstrap_ci(pos, neg, n_boot=400, seed=1)
    assert lo < point < hi
    assert 0.0 <= lo < hi <= 1.0
    assert bootstrap_ci(pos, neg, n_boot=400, seed=1) == (lo, hi)
    assert bootstrap_ci(pos, neg, n_boot=400, seed=2) != (lo, hi)
    # Custom statistic and narrower interval for a larger alpha.
    lo2, hi2 = bootstrap_ci(pos, neg, statistic=tpr_at_fpr, n_boot=200, alpha=0.5, seed=3)
    assert lo2 <= hi2
    assert (hi - lo) > 0.0


def test_bootstrap_ci_degenerate_separable() -> None:
    assert bootstrap_ci(np.arange(10.0) + 50, np.arange(10.0), n_boot=50) == (1.0, 1.0)


def test_bootstrap_mean_ci(rng: np.random.Generator) -> None:
    values = rng.normal(3.0, 1.0, 50)
    lo, hi = bootstrap_mean_ci(values, n_boot=500, seed=0)
    assert lo < values.mean() < hi
    assert bootstrap_mean_ci(values, n_boot=500, seed=0) == (lo, hi)
    with pytest.raises(ValueError, match="finite"):
        bootstrap_mean_ci(np.array([np.nan]))


def _handmade(x: FloatArray) -> Trajectories:
    n = x.shape[0]
    return Trajectories(
        t=np.arange(n, dtype=np.float64) * 0.5,
        r=np.zeros(n),
        x=x,
        sigma=0.0,
        dt=0.01,
        sample_every=50,
        seed=0,
    )


def _noisy_runs(n_samples: int, tips: list[int | None], seed: int) -> FloatArray:
    rng = np.random.default_rng(seed)
    x = 1.0 + 0.03 * rng.standard_normal((n_samples, len(tips)))
    for j, tip in enumerate(tips):
        if tip is not None:
            x[tip:, j] = -1.0
    return x


def test_evaluate_pair_tipping_truncation_and_validity_rules() -> None:
    cfg = IndicatorConfig(window=100, detrend_window=25)  # step = 2, horizon = 600
    n = 1000
    # Ramp: A never tips; B tips at 300 (early, still valid); C at 120 (too early: invalid);
    # D at 700 (after the horizon: not early). Null: one run tips at 500.
    ramp = _handmade(_noisy_runs(n, [None, 300, 120, 700], seed=1))
    null = _handmade(_noisy_runs(n, [None, None, 500, None], seed=2))
    res = evaluate_pair(ramp, null, cfg)
    assert res.frac_ramp_tipped_early == pytest.approx(0.5)  # B and C tipped before index 600
    assert res.frac_null_tipped == pytest.approx(0.25)
    assert res.n_valid_ramp == 3  # C has no usable window
    assert res.n_valid_null == 4
    assert res.tau_ramp_var.shape == (3,)
    assert res.tau_null_ar1.shape == (4,)
    taus = run_taus(ramp.x, cfg)
    assert np.isnan(taus.tau_var[2])
    np.testing.assert_array_equal(taus.tip_index, [n, 300, 120, 700])


def test_evaluate_pair_min_points_boundary() -> None:
    cfg = IndicatorConfig(window=100, detrend_window=25)
    n = 1000
    # stop = tip - 25; points = len(range(100, stop, 2)) = 15 needs stop in [129, 130].
    x = _noisy_runs(n, [155, 154], seed=3)  # stop = 130 (15 points) and 129 (15 points)
    taus = run_taus(x, cfg)
    assert np.isfinite(taus.tau_var).all()
    x = _noisy_runs(n, [153], seed=3)  # stop = 128 -> 14 points
    assert np.isnan(run_taus(x, cfg).tau_var[0])


def test_evaluate_pair_all_invalid_gives_nan_metrics() -> None:
    cfg = IndicatorConfig(window=100, detrend_window=25)
    ramp = _handmade(_noisy_runs(1000, [110, 120], seed=4))
    null = _handmade(_noisy_runs(1000, [None, None], seed=5))
    res = evaluate_pair(ramp, null, cfg)
    assert res.n_valid_ramp == 0
    assert np.isnan(res.auc_var)
    assert np.isnan(res.tpr_ar1)
    assert res.frac_ramp_tipped_early == 1.0


def test_evaluate_pair_rejects_mismatched_lengths() -> None:
    cfg = IndicatorConfig(window=50, detrend_window=10)
    with pytest.raises(ValueError, match="same number"):
        evaluate_pair(
            _handmade(_noisy_runs(500, [None], 1)), _handmade(_noisy_runs(600, [None], 1)), cfg
        )


def test_run_experiment_is_reproducible_and_short_ramp_works(baseline: ExperimentConfig) -> None:
    sim = baseline.sim.model_copy(update={"n_runs": 40, "duration": 400.0})
    ind = IndicatorConfig.for_sweep(sim.duration, sim.sample_interval)
    a = run_experiment(sim, ind, seed=9)
    b = run_experiment(sim, ind, seed=9)
    np.testing.assert_array_equal(a.ramp.x, b.ramp.x)
    assert a.result.auc_ar1 == b.result.auc_ar1
    assert a.result.auc_var > 0.7
    assert not np.array_equal(a.ramp.x[:, :1], a.null.x[:, :1])  # independent streams
    assert a.ramp.n_runs == a.null.n_runs == 40


@pytest.mark.slow
def test_baseline_experiment(baseline: ExperimentConfig) -> None:
    exp = run_experiment(baseline.sim, baseline.indicators, seed=42)
    res = exp.result
    assert res.auc_ar1 > 0.95
    assert res.auc_var > 0.95
    assert np.median(res.tau_ramp_var) > np.median(res.tau_null_var) + 0.5
    assert np.median(res.tau_ramp_ar1) > np.median(res.tau_null_ar1) + 0.5
    assert res.frac_null_tipped == 0.0
    assert res.frac_ramp_tipped_early < 0.10
    assert res.n_valid_ramp > 0.9 * baseline.sim.n_runs
