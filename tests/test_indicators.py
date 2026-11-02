"""Tests of detrending, rolling indicators and Kendall tau."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy import stats

from tipping.indicators import (
    compute_indicators,
    detrend,
    kendall_tau_per_run,
    rolling_ar1,
    rolling_variance,
)

FloatArray = NDArray[np.float64]


def _naive_rolling(a: FloatArray, window: int, fn: Callable[[FloatArray], float]) -> FloatArray:
    out = np.full(a.shape, np.nan)
    for i in range(window - 1, a.shape[0]):
        for j in range(a.shape[1]):
            out[i, j] = fn(a[i - window + 1 : i + 1, j])
    return out


def _ar1_series(phi: float, n: int, seed: int, n_runs: int = 1) -> FloatArray:
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((n, n_runs))
    x = np.zeros((n, n_runs))
    for i in range(1, n):
        x[i] = phi * x[i - 1] + noise[i]
    return x


def test_detrend_removes_linear_trend_in_the_interior() -> None:
    n, w = 200, 21
    x = 0.3 * np.arange(n, dtype=float)
    resid = detrend(x, w)
    np.testing.assert_allclose(resid[w:-w], 0.0, atol=1e-9)
    assert resid.shape == x.shape


def test_detrend_constant_and_2d() -> None:
    x = np.full((50, 3), 2.5)
    np.testing.assert_allclose(detrend(x, 9), 0.0, atol=1e-12)
    with pytest.raises(ValueError, match="window"):
        detrend(x, 0)


def test_detrend_matches_explicit_moving_average() -> None:
    rng = np.random.default_rng(0)
    x = rng.standard_normal(60)
    w = 5
    padded = np.concatenate([np.full(2, x[0]), x, np.full(2, x[-1])])
    expected = x - np.convolve(padded, np.ones(w) / w, mode="valid")
    np.testing.assert_allclose(detrend(x, w), expected, atol=1e-12)


def test_rolling_variance_equals_naive() -> None:
    rng = np.random.default_rng(1)
    a = rng.standard_normal((60, 4)).cumsum(axis=0) * 0.1 + 1000.0  # large offset on purpose
    fast = rolling_variance(a, 12)
    slow = _naive_rolling(a, 12, lambda w: float(np.var(w, ddof=1)))
    np.testing.assert_allclose(fast, slow, rtol=1e-8, atol=1e-10)
    assert np.isnan(fast[:11]).all()
    assert np.isfinite(fast[11:]).all()


def test_rolling_ar1_equals_naive() -> None:
    rng = np.random.default_rng(2)
    a = rng.standard_normal((60, 4)).cumsum(axis=0) * 0.1 + 1000.0
    fast = rolling_ar1(a, 12)
    slow = _naive_rolling(a, 12, lambda w: np.corrcoef(w[:-1], w[1:])[0, 1])
    np.testing.assert_allclose(fast, slow, atol=1e-8)
    assert np.isnan(fast[:11]).all()


def test_rolling_indicators_accept_1d() -> None:
    rng = np.random.default_rng(3)
    a = rng.standard_normal(80)
    np.testing.assert_allclose(
        rolling_variance(a, 10), rolling_variance(a[:, None], 10)[:, 0], equal_nan=True
    )
    np.testing.assert_allclose(
        rolling_ar1(a, 10), rolling_ar1(a[:, None], 10)[:, 0], equal_nan=True
    )


def test_rolling_ar1_recovers_known_coefficient() -> None:
    x = _ar1_series(0.7, 30_000, seed=4, n_runs=3)
    ar1 = rolling_ar1(x, 5000)
    assert np.nanmean(ar1) == pytest.approx(0.7, abs=0.02)
    var = rolling_variance(x, 5000)
    assert np.nanmean(var) == pytest.approx(1.0 / (1 - 0.7**2), rel=0.05)


def test_rolling_ar1_constant_window_is_nan() -> None:
    out = rolling_ar1(np.ones((20, 1)), 6)
    assert np.isnan(out).all()


def test_window_validation() -> None:
    with pytest.raises(ValueError, match="longer"):
        rolling_variance(np.zeros(5), 6)
    with pytest.raises(ValueError, match="window"):
        rolling_ar1(np.zeros(10), 2)


def test_compute_indicators_pipeline() -> None:
    x = _ar1_series(0.5, 2000, seed=5, n_runs=2) + np.linspace(0, 5, 2000)[:, None]
    res = compute_indicators(x, 200, 50)
    assert res.residual.shape == res.variance.shape == res.ar1.shape == x.shape
    np.testing.assert_allclose(res.residual, detrend(x, 50))
    np.testing.assert_allclose(res.variance, rolling_variance(res.residual, 200), equal_nan=True)
    residual, variance, ar1 = res  # NamedTuple unpacking
    assert residual is res.residual
    assert variance is res.variance
    assert ar1 is res.ar1


def test_kendall_tau_per_run_monotone_and_reference() -> None:
    n = 300
    t = np.arange(n, dtype=float)
    rng = np.random.default_rng(6)
    ind = np.column_stack([t, -t, rng.standard_normal(n)])
    stop = np.array([n, n, n])
    tau = kendall_tau_per_run(ind, start=50, stop_per_run=stop, step=5)
    assert tau[0] == pytest.approx(1.0)
    assert tau[1] == pytest.approx(-1.0)
    idx = np.arange(50, n, 5)
    assert tau[2] == pytest.approx(stats.kendalltau(idx, ind[idx, 2]).statistic)


def test_kendall_tau_per_run_truncation_and_invalid_runs() -> None:
    n = 300
    ind = np.tile(np.arange(n, dtype=float)[:, None], (1, 3))
    # Run 0: plenty of points; run 1: only 10 points (< 15); run 2: stop below start.
    stop = np.array([200, 100, 40])
    tau = kendall_tau_per_run(ind, start=50, stop_per_run=stop, step=5, min_points=15)
    assert tau[0] == pytest.approx(1.0)
    assert np.isnan(tau[1])
    assert np.isnan(tau[2])
    # Lowering the threshold makes run 1 valid.
    assert kendall_tau_per_run(ind, 50, stop, 5, min_points=10)[1] == pytest.approx(1.0)


def test_kendall_tau_per_run_nonfinite_and_bad_args() -> None:
    ind = np.arange(100, dtype=float)[:, None].copy()
    ind[60, 0] = np.nan
    stop = np.array([100])
    assert np.isnan(kendall_tau_per_run(ind, 0, stop, 1)[0])
    with pytest.raises(ValueError, match="stop_per_run"):
        kendall_tau_per_run(ind, 0, np.array([1, 2]), 1)
    with pytest.raises(ValueError, match="step"):
        kendall_tau_per_run(ind, 0, stop, 0)
