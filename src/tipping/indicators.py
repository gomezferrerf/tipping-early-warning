"""Early-warning indicators: detrending, rolling variance, rolling lag-1 autocorrelation.

All functions operate on arrays of shape ``(n_samples,)`` or ``(n_samples, n_runs)`` along the
first axis and are vectorised across runs. The rolling statistics use cumulative sums, so their
cost does not depend on the window length; they are equivalent (to floating-point accuracy)
to the naive per-window computation, which the test suite checks.

Inputs must be free of NaN: a single NaN contaminates the cumulative sums and therefore every
later window of that run. The simulator never produces NaN.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage, stats

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]


class Indicators(NamedTuple):
    """Result of :func:`compute_indicators`.

    Attributes
    ----------
    residual : numpy.ndarray
        Detrended series.
    variance : numpy.ndarray
        Rolling variance of the residual (``nan`` before the first full window).
    ar1 : numpy.ndarray
        Rolling lag-1 autocorrelation of the residual (``nan`` before the first full window).
    """

    residual: FloatArray
    variance: FloatArray
    ar1: FloatArray


def _validate_window(window: int, n_samples: int, minimum: int) -> None:
    if window < minimum:
        msg = f"window must be >= {minimum}, got {window}"
        raise ValueError(msg)
    if window > n_samples:
        msg = f"window ({window}) is longer than the series ({n_samples} samples)"
        raise ValueError(msg)


def _prefix_sums(values: FloatArray) -> FloatArray:
    """Cumulative sums along axis 0 with a leading row of zeros."""
    out = np.zeros((values.shape[0] + 1, *values.shape[1:]))
    np.cumsum(values, axis=0, out=out[1:])
    return out


def detrend(x: FloatArray, window: int) -> FloatArray:
    """Subtract a uniform moving average (the slow trend) from the series.

    The moving average is centred, ``window`` samples long, and uses
    ``mode="nearest"`` at the boundaries.

    Parameters
    ----------
    x : numpy.ndarray
        Series, shape ``(n_samples,)`` or ``(n_samples, n_runs)``.
    window : int
        Moving-average length in samples.

    Returns
    -------
    numpy.ndarray
        Residual ``x - moving_average(x)`` with the same shape as ``x``.

    Raises
    ------
    ValueError
        If ``window < 1``.
    """
    if window < 1:
        msg = f"window must be >= 1, got {window}"
        raise ValueError(msg)
    trend = ndimage.uniform_filter1d(x, size=window, axis=0, mode="nearest")
    residual: FloatArray = x - trend
    return residual


def rolling_variance(resid: FloatArray, window: int) -> FloatArray:
    """Compute the rolling sample variance (``ddof=1``) over a trailing window.

    Parameters
    ----------
    resid : numpy.ndarray
        Series, shape ``(n_samples,)`` or ``(n_samples, n_runs)``; must not contain NaN.
    window : int
        Window length in samples (``>= 2``).

    Returns
    -------
    numpy.ndarray
        Same shape as ``resid``; entry ``i`` is the variance of ``resid[i-window+1 : i+1]``,
        and the first ``window - 1`` entries are ``nan``.
    """
    n = resid.shape[0]
    _validate_window(window, n, 2)
    centred = resid - np.nanmean(resid, axis=0)
    s1 = _prefix_sums(centred)
    s2 = _prefix_sums(centred**2)
    sum1 = s1[window:] - s1[:-window]
    sum2 = s2[window:] - s2[:-window]
    var = np.maximum(sum2 - sum1**2 / window, 0.0) / (window - 1)
    out: FloatArray = np.full(resid.shape, np.nan)
    out[window - 1 :] = var
    return out


def rolling_ar1(resid: FloatArray, window: int) -> FloatArray:
    """Compute the rolling lag-1 autocorrelation over a trailing window.

    For each window the statistic is the Pearson correlation between ``w[:-1]`` and ``w[1:]``
    (the window and its one-step shift, each with its own mean), as computed by
    ``numpy.corrcoef`` on the window.

    Parameters
    ----------
    resid : numpy.ndarray
        Series, shape ``(n_samples,)`` or ``(n_samples, n_runs)``; must not contain NaN.
    window : int
        Window length in samples (``>= 3``).

    Returns
    -------
    numpy.ndarray
        Same shape as ``resid``; the first ``window - 1`` entries are ``nan``, as are windows in
        which the series is constant.
    """
    n = resid.shape[0]
    _validate_window(window, n, 3)
    v = resid - np.nanmean(resid, axis=0)
    lead, lag = v[:-1], v[1:]
    s_lead, s_lag = _prefix_sums(lead), _prefix_sums(lag)
    s_ll, s_gg = _prefix_sums(lead**2), _prefix_sums(lag**2)
    s_lg = _prefix_sums(lead * lag)
    m = window - 1  # number of (w[j], w[j+1]) pairs per window
    # Window ending at sample i holds pairs j = i-m .. i-1, i.e. prefix rows [i-m, i).
    a = s_lead[m:] - s_lead[: n - m]
    b = s_lag[m:] - s_lag[: n - m]
    aa = s_ll[m:] - s_ll[: n - m]
    bb = s_gg[m:] - s_gg[: n - m]
    ab = s_lg[m:] - s_lg[: n - m]
    cov = ab - a * b / m
    var_a = aa - a**2 / m
    var_b = bb - b**2 / m
    denom = np.sqrt(np.maximum(var_a, 0.0) * np.maximum(var_b, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        ar1 = np.where(denom > 0.0, cov / denom, np.nan)
    out: FloatArray = np.full(resid.shape, np.nan)
    out[window - 1 :] = np.clip(ar1, -1.0, 1.0)
    return out


def kendall_tau_per_run(
    indicator: FloatArray,
    start: int,
    stop_per_run: IntArray,
    step: int,
    min_points: int = 15,
) -> FloatArray:
    """Kendall's tau between an indicator and time, run by run.

    For run ``j`` the indicator is subsampled at indices ``start, start + step, ...`` strictly
    below ``stop_per_run[j]`` and correlated (Kendall's tau-b) with the sample index.

    Parameters
    ----------
    indicator : numpy.ndarray
        Indicator series, shape ``(n_samples, n_runs)``.
    start : int
        First index used (typically the window length, where the first full window ends).
    stop_per_run : numpy.ndarray
        Exclusive end index per run, shape ``(n_runs,)``; may be below ``start``.
    step : int
        Subsampling step in samples.
    min_points : int, default 15
        Runs with fewer subsampled points are invalid.

    Returns
    -------
    numpy.ndarray
        Tau per run, shape ``(n_runs,)``; ``nan`` for invalid runs and for runs whose subsampled
        values contain non-finite entries.
    """
    n_samples, n_runs = indicator.shape
    if stop_per_run.shape != (n_runs,):
        msg = f"stop_per_run must have shape ({n_runs},), got {stop_per_run.shape}"
        raise ValueError(msg)
    if step < 1:
        msg = f"step must be >= 1, got {step}"
        raise ValueError(msg)
    tau = np.full(n_runs, np.nan)
    for j in range(n_runs):
        stop = min(int(stop_per_run[j]), n_samples)
        idx = np.arange(start, stop, step)
        if idx.size < min_points:
            continue
        values = indicator[idx, j]
        if not np.all(np.isfinite(values)):
            continue
        tau[j] = float(stats.kendalltau(idx, values).statistic)
    return tau


def compute_indicators(x: FloatArray, window: int, detrend_window: int) -> Indicators:
    """Detrend a series and compute its rolling variance and lag-1 autocorrelation.

    Parameters
    ----------
    x : numpy.ndarray
        Series, shape ``(n_samples,)`` or ``(n_samples, n_runs)``; must not contain NaN.
    window : int
        Rolling-window length in samples.
    detrend_window : int
        Moving-average length in samples used for detrending.

    Returns
    -------
    Indicators
        Named tuple ``(residual, variance, ar1)``.
    """
    residual = detrend(x, detrend_window)
    return Indicators(
        residual=residual,
        variance=rolling_variance(residual, window),
        ar1=rolling_ar1(residual, window),
    )
