"""Overdamped bistable system with an imperfect pitchfork unfolding.

The deterministic dynamics are ``dx/dt = f(x, r) = r + x - x**3 = -dV/dx`` with the potential
``V(x, r) = -r x - x**2 / 2 + x**4 / 4``. Equilibria solve ``x**3 - x - r = 0``. The growth
rate at an equilibrium is ``lambda(x) = f'(x) = 1 - 3 x**2``; it is negative (stable) iff
``|x| > 1/sqrt(3)``.

Two saddle-node bifurcations (folds, a.k.a. tangent bifurcations) occur at ``r = +-FOLD_R`` with
``FOLD_R = 2 / (3 sqrt(3))``. Three real equilibria exist iff ``|r| < FOLD_R``. They are computed in
closed form: the trigonometric solution for ``|r| <= FOLD_R`` and Cardano's formula with real cube
roots otherwise. No numerical root finder is used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, overload

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

FOLD_R: float = 2.0 / (3.0 * math.sqrt(3.0))
"""Control-parameter value ``r_c = 2 / (3 sqrt(3))`` of the two saddle-node bifurcations."""

FOLD_X: float = 1.0 / math.sqrt(3.0)
"""Magnitude ``1 / sqrt(3)`` of the double root at either fold."""

_OUTER_ROOT = 2.0 / math.sqrt(3.0)
_TRIG_SCALE = 3.0 * math.sqrt(3.0) / 2.0
# ``arccos`` is ill-conditioned at +-1, so r within this distance of a fold is snapped onto it.
_FOLD_SNAP_TOL = 1e-12
# |growth rate| below this value marks a (numerically) double root.
_SEMISTABLE_TOL = 1e-9


@dataclass(frozen=True)
class Equilibrium:
    """An equilibrium of the deterministic dynamics.

    Attributes
    ----------
    x : float
        Position of the equilibrium.
    growth_rate : float
        Linear growth rate ``1 - 3 x**2`` at the equilibrium.
    kind : {"stable", "unstable", "semistable"}
        ``"semistable"`` marks the double root at a fold (``|growth_rate| < 1e-9``).
    """

    x: float
    growth_rate: float
    kind: Literal["stable", "unstable", "semistable"]


@overload
def drift(x: float, r: float) -> float: ...
@overload
def drift(x: FloatArray, r: float | FloatArray) -> FloatArray: ...
@overload
def drift(x: float, r: FloatArray) -> FloatArray: ...
def drift(x: float | FloatArray, r: float | FloatArray) -> float | FloatArray:
    """Deterministic drift ``f(x, r) = r + x - x**3``.

    Parameters
    ----------
    x : float or numpy.ndarray
        State.
    r : float or numpy.ndarray
        Control parameter (broadcast against ``x``).

    Returns
    -------
    float or numpy.ndarray
        ``r + x - x**3``.
    """
    return r + x - x**3


@overload
def potential(x: float, r: float) -> float: ...
@overload
def potential(x: FloatArray, r: float | FloatArray) -> FloatArray: ...
@overload
def potential(x: float, r: FloatArray) -> FloatArray: ...
def potential(x: float | FloatArray, r: float | FloatArray) -> float | FloatArray:
    """Potential ``V(x, r) = -r x - x**2 / 2 + x**4 / 4`` with ``f = -dV/dx``.

    Parameters
    ----------
    x : float or numpy.ndarray
        State.
    r : float or numpy.ndarray
        Control parameter (broadcast against ``x``).

    Returns
    -------
    float or numpy.ndarray
        Potential energy.
    """
    return -r * x - x**2 / 2.0 + x**4 / 4.0


@overload
def growth_rate(x: float) -> float: ...
@overload
def growth_rate(x: FloatArray) -> FloatArray: ...
def growth_rate(x: float | FloatArray) -> float | FloatArray:
    """Linear growth rate ``f'(x) = 1 - 3 x**2`` (independent of ``r``).

    Parameters
    ----------
    x : float or numpy.ndarray
        State, typically an equilibrium.

    Returns
    -------
    float or numpy.ndarray
        ``1 - 3 x**2``; negative where the equilibrium is stable.
    """
    return 1.0 - 3.0 * x**2


def _three_roots(r: FloatArray) -> FloatArray:
    """Trigonometric roots as a ``(3, n)`` array ordered ``k = 0, 1, 2`` (descending).

    Only meaningful where ``|r| <= FOLD_R``; elsewhere the ``arccos`` argument is clipped.
    Within ``_FOLD_SNAP_TOL`` of a fold the exact roots (with the double root repeated) are used.
    """
    theta = np.arccos(np.clip(_TRIG_SCALE * r, -1.0, 1.0)) / 3.0
    k = np.arange(3, dtype=np.float64)[:, None]
    roots: FloatArray = _OUTER_ROOT * np.cos(theta[None, :] - 2.0 * np.pi * k / 3.0)
    at_upper_fold = np.abs(r - FOLD_R) <= _FOLD_SNAP_TOL
    at_lower_fold = np.abs(r + FOLD_R) <= _FOLD_SNAP_TOL
    roots[:, at_upper_fold] = np.array([_OUTER_ROOT, -FOLD_X, -FOLD_X])[:, None]
    roots[:, at_lower_fold] = np.array([FOLD_X, FOLD_X, -_OUTER_ROOT])[:, None]
    return roots


def _single_root(r: FloatArray) -> FloatArray:
    """Compute the unique real root by Cardano's formula (valid where ``|r| > FOLD_R``).

    Uses ``x = cbrt(r/2 + s) + cbrt(r/2 - s)`` with ``s = sqrt(r**2/4 - 1/27)`` and real cube
    roots (``numpy.cbrt``). The cubic is odd in ``(x, r)``, so the formula is evaluated at
    ``|r|`` and the sign restored, which avoids cancellation for negative ``r``.
    """
    a = np.abs(r) / 2.0
    s = np.sqrt(np.maximum(a**2 - 1.0 / 27.0, 0.0))
    root: FloatArray = np.sign(r) * (np.cbrt(a + s) + np.cbrt(a - s))
    return root


def _in_three_root_regime(r: FloatArray) -> NDArray[np.bool_]:
    mask: NDArray[np.bool_] = np.abs(r) <= FOLD_R + _FOLD_SNAP_TOL
    return mask


def equilibria(r: float) -> FloatArray:
    """All real equilibria of ``x**3 - x - r = 0`` in closed form, sorted ascending.

    For ``|r| <= FOLD_R`` the three real roots come from the trigonometric solution
    ``x_k = (2/sqrt(3)) cos(arccos(3 sqrt(3) r / 2) / 3 - 2 pi k / 3)``. At ``|r| == FOLD_R`` the
    double root is returned twice. For ``|r| > FOLD_R`` the single real root comes from
    Cardano's formula with real cube roots. ``r`` within ``1e-12`` of a fold is treated as
    exactly on the fold.

    Parameters
    ----------
    r : float
        Control parameter.

    Returns
    -------
    numpy.ndarray
        Array of 3 roots (``|r| <= FOLD_R``) or 1 root (``|r| > FOLD_R``), ascending.

    Raises
    ------
    ValueError
        If ``r`` is not finite.
    """
    if not math.isfinite(r):
        msg = f"r must be finite, got {r!r}"
        raise ValueError(msg)
    arr = np.array([float(r)])
    if _in_three_root_regime(arr)[0]:
        result: FloatArray = _three_roots(arr)[::-1, 0].copy()
        return result
    return _single_root(arr)


def classify_equilibria(r: float) -> list[Equilibrium]:
    """Equilibria at ``r`` with their stability, sorted by position.

    Parameters
    ----------
    r : float
        Control parameter.

    Returns
    -------
    list of Equilibrium
        One entry per root returned by :func:`equilibria`. Roots with
        ``|growth_rate| < 1e-9`` are ``"semistable"`` (the double root at a fold); otherwise
        ``"stable"`` if the growth rate is negative and ``"unstable"`` if positive.
    """
    out: list[Equilibrium] = []
    for x in equilibria(r):
        lam = float(growth_rate(float(x)))
        kind: Literal["stable", "unstable", "semistable"]
        if abs(lam) < _SEMISTABLE_TOL:
            kind = "semistable"
        elif lam < 0.0:
            kind = "stable"
        else:
            kind = "unstable"
        out.append(Equilibrium(x=float(x), growth_rate=lam, kind=kind))
    return out


def _branch(
    r: float | FloatArray, which: Literal["upper", "middle", "lower"]
) -> float | FloatArray:
    scalar = np.ndim(r) == 0
    arr = np.atleast_1d(np.asarray(r, dtype=np.float64))
    out: FloatArray = np.full(arr.shape, np.nan)
    inner = _in_three_root_regime(arr)
    if inner.any():
        row = {"upper": 0, "middle": 1, "lower": 2}[which]
        out[inner] = _three_roots(arr[inner])[row]
    if which == "upper":
        outer = arr > FOLD_R + _FOLD_SNAP_TOL
    elif which == "lower":
        outer = arr < -FOLD_R - _FOLD_SNAP_TOL
    else:
        outer = np.zeros(arr.shape, dtype=bool)
    if outer.any():
        out[outer] = _single_root(arr[outer])
    return float(out[0]) if scalar else out


@overload
def upper_branch(r: float) -> float: ...
@overload
def upper_branch(r: FloatArray) -> FloatArray: ...
def upper_branch(r: float | FloatArray) -> float | FloatArray:
    """Largest equilibrium (the upper, initially stable branch) as a function of ``r``.

    Parameters
    ----------
    r : float or numpy.ndarray
        Control parameter.

    Returns
    -------
    float or numpy.ndarray
        The largest root where it belongs to the upper branch, i.e. for ``r >= -FOLD_R``;
        ``nan`` for ``r < -FOLD_R`` where the upper branch no longer exists.
    """
    return _branch(r, "upper")


@overload
def lower_branch(r: float) -> float: ...
@overload
def lower_branch(r: FloatArray) -> FloatArray: ...
def lower_branch(r: float | FloatArray) -> float | FloatArray:
    """Smallest equilibrium (the lower, stable branch) as a function of ``r``.

    Parameters
    ----------
    r : float or numpy.ndarray
        Control parameter.

    Returns
    -------
    float or numpy.ndarray
        The smallest root where it belongs to the lower branch, i.e. for ``r <= FOLD_R``;
        ``nan`` for ``r > FOLD_R``.
    """
    return _branch(r, "lower")


@overload
def middle_branch(r: float) -> float: ...
@overload
def middle_branch(r: FloatArray) -> FloatArray: ...
def middle_branch(r: float | FloatArray) -> float | FloatArray:
    """Middle (unstable) equilibrium, which exists only for ``|r| <= FOLD_R``.

    Parameters
    ----------
    r : float or numpy.ndarray
        Control parameter.

    Returns
    -------
    float or numpy.ndarray
        The middle root for ``|r| <= FOLD_R``; ``nan`` otherwise.
    """
    return _branch(r, "middle")
