"""Linear (Ornstein-Uhlenbeck) theory for fluctuations around a stable equilibrium.

Linearising ``dx = f(x, r) dt + sigma dW`` around a stable equilibrium with growth rate
``lambda < 0`` gives an Ornstein-Uhlenbeck process with relaxation rate ``|lambda|``:

* stationary variance ``sigma**2 / (2 |lambda|)``,
* autocorrelation function ``exp(lambda * tau)``,
* lag-1 autocorrelation of the series sampled every ``dt``: ``phi = exp(lambda * dt)``.

Both indicators grow as the fold is approached (``lambda -> 0``): critical slowing down. The
linear theory is the ``sigma -> 0`` limit; it degrades close to the fold and for large noise.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from tipping.model import growth_rate, upper_branch

FloatArray = NDArray[np.float64]


def _check_stable(rate: float | FloatArray) -> None:
    if np.any(np.asarray(rate) > 0.0):
        msg = "growth_rate must be <= 0 (stable or marginal equilibrium)"
        raise ValueError(msg)


def ou_variance(sigma: float, growth_rate: float | FloatArray) -> float | FloatArray:
    """Stationary variance of the linearised process, ``sigma**2 / (2 |lambda|)``.

    Parameters
    ----------
    sigma : float
        Noise amplitude.
    growth_rate : float or numpy.ndarray
        Linear growth rate ``lambda <= 0`` of the equilibrium.

    Returns
    -------
    float or numpy.ndarray
        Variance; ``inf`` at the marginal case ``lambda == 0``.

    Raises
    ------
    ValueError
        If any ``growth_rate`` is positive (unstable equilibrium).
    """
    _check_stable(growth_rate)
    with np.errstate(divide="ignore"):
        return sigma**2 / (2.0 * np.abs(growth_rate))


def ou_acf(growth_rate: float | FloatArray, lag: float | FloatArray) -> float | FloatArray:
    """Autocorrelation ``exp(lambda * |lag|)`` of the linearised process.

    Parameters
    ----------
    growth_rate : float or numpy.ndarray
        Linear growth rate ``lambda <= 0``.
    lag : float or numpy.ndarray
        Time lag (its sign is irrelevant).

    Returns
    -------
    float or numpy.ndarray
        Autocorrelation at ``lag``.

    Raises
    ------
    ValueError
        If any ``growth_rate`` is positive.
    """
    _check_stable(growth_rate)
    return np.exp(growth_rate * np.abs(lag))


def ou_ar1(growth_rate: float | FloatArray, dt: float) -> float | FloatArray:
    """Lag-1 autocorrelation ``exp(lambda * dt)`` of the process sampled every ``dt``.

    Parameters
    ----------
    growth_rate : float or numpy.ndarray
        Linear growth rate ``lambda <= 0``.
    dt : float
        Sampling interval.

    Returns
    -------
    float or numpy.ndarray
        AR(1) coefficient ``phi``.
    """
    return ou_acf(growth_rate, dt)


def predicted_indicators(r: float, sigma: float, dt: float) -> tuple[float, float]:
    """Predicted (variance, lag-1 autocorrelation) on the upper branch at parameter ``r``.

    Parameters
    ----------
    r : float
        Control parameter; must satisfy ``r >= -FOLD_R`` so that the upper branch exists.
    sigma : float
        Noise amplitude.
    dt : float
        Sampling interval of the observed series.

    Returns
    -------
    tuple of float
        ``(variance, ar1)``. Exactly at the fold the variance is ``inf`` and ``ar1`` is 1.

    Raises
    ------
    ValueError
        If the upper branch does not exist at ``r``.
    """
    x_star = upper_branch(float(r))
    if np.isnan(x_star):
        msg = f"the upper branch does not exist at r={r!r} (it is lost at r=-FOLD_R)"
        raise ValueError(msg)
    # Rounding can leave a ~1e-16 positive rate exactly at the fold.
    rate = min(float(growth_rate(x_star)), 0.0)
    return float(ou_variance(sigma, rate)), float(ou_ar1(rate, dt))
