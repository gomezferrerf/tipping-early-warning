"""Tests of the closed-form equilibria and stability classification."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tipping.model import (
    FOLD_R,
    FOLD_X,
    classify_equilibria,
    drift,
    equilibria,
    growth_rate,
    lower_branch,
    middle_branch,
    potential,
    upper_branch,
)

R_GRID = [
    *np.linspace(-0.9, 0.9, 37).tolist(),
    0.0,
    0.2,
    -0.2,
    FOLD_R,
    -FOLD_R,
    FOLD_R * (1 - 1e-6),
    FOLD_R * (1 + 1e-6),
    -FOLD_R * (1 - 1e-6),
    -FOLD_R * (1 + 1e-6),
]


def test_fold_constants() -> None:
    assert pytest.approx(0.3849001794597505) == FOLD_R
    assert pytest.approx(0.5773502691896258) == FOLD_X
    assert pytest.approx(2.0 / (3.0 * math.sqrt(3.0))) == FOLD_R


@pytest.mark.parametrize("r", R_GRID)
def test_equilibria_match_numpy_roots(r: float) -> None:
    roots = np.roots([1.0, 0.0, -1.0, -r])
    real = np.sort(roots[np.abs(roots.imag) < 1e-6].real)
    ours = equilibria(r)
    if abs(r) <= FOLD_R:
        assert ours.shape == (3,)
        # np.roots is itself only accurate to ~1e-8 at a double root.
        np.testing.assert_allclose(ours, np.sort(roots.real), atol=1e-6)
    else:
        assert ours.shape == (1,)
        np.testing.assert_allclose(ours, real, atol=1e-9)
    # Residual of the cubic is the exact criterion.
    assert np.max(np.abs(ours**3 - ours - r)) < 1e-9
    assert np.all(np.diff(ours) >= 0.0)


def test_equilibria_at_fold_repeat_double_root() -> None:
    np.testing.assert_allclose(equilibria(FOLD_R), [-FOLD_X, -FOLD_X, 2 * FOLD_X], atol=1e-14)
    np.testing.assert_allclose(equilibria(-FOLD_R), [-2 * FOLD_X, FOLD_X, FOLD_X], atol=1e-14)


def test_reference_roots() -> None:
    np.testing.assert_allclose(equilibria(0.2), [-0.8789, -0.2091, 1.0880], atol=5e-5)
    np.testing.assert_allclose(equilibria(0.0), [-1.0, 0.0, 1.0], atol=1e-12)


def test_equilibria_odd_symmetry() -> None:
    for r in (0.05, 0.3, 0.7):
        np.testing.assert_allclose(equilibria(-r), -equilibria(r)[::-1], atol=1e-12)


def test_equilibria_rejects_nonfinite() -> None:
    with pytest.raises(ValueError, match="finite"):
        equilibria(float("nan"))


@pytest.mark.parametrize(
    ("r", "x_star", "lam"),
    [
        (0.0, 1.0000, -2.0000),
        (-0.2, 0.8789, -1.3173),
        (-0.3, 0.7865, -0.8557),
        (-0.35, 0.7140, -0.5294),
        (-0.38, 0.6298, -0.1898),
    ],
)
def test_upper_branch_reference_values(r: float, x_star: float, lam: float) -> None:
    x = upper_branch(r)
    assert x == pytest.approx(x_star, abs=5e-5)
    assert growth_rate(x) == pytest.approx(lam, abs=5e-5)


def test_stability_classification_three_roots() -> None:
    kinds = [e.kind for e in classify_equilibria(0.0)]
    assert kinds == ["stable", "unstable", "stable"]
    eq = classify_equilibria(0.0)
    assert [e.x for e in eq] == pytest.approx([-1.0, 0.0, 1.0], abs=1e-12)
    assert eq[1].growth_rate == pytest.approx(1.0, abs=1e-9)
    assert eq[0].growth_rate == pytest.approx(-2.0)


def test_stability_classification_single_root_is_stable() -> None:
    for r in (-0.5, 0.5, 2.0, -3.0):
        (only,) = classify_equilibria(r)
        assert only.kind == "stable"
        assert only.growth_rate < 0.0


@pytest.mark.parametrize("r", [FOLD_R, -FOLD_R])
def test_double_root_is_semistable(r: float) -> None:
    eq = classify_equilibria(r)
    kinds = sorted(e.kind for e in eq)
    assert kinds == ["semistable", "semistable", "stable"]
    for e in eq:
        if e.kind == "semistable":
            assert abs(e.growth_rate) < 1e-9
            assert abs(e.x) == pytest.approx(FOLD_X)


def test_just_inside_fold_has_stable_and_unstable_pair() -> None:
    kinds = [e.kind for e in classify_equilibria(-FOLD_R * (1 - 1e-6))]
    assert sorted(kinds) == ["stable", "stable", "unstable"]


def test_hysteresis_jump_values() -> None:
    # Ramping r down: the upper branch ends at -r_c on the double root x = +1/sqrt(3).
    assert upper_branch(-FOLD_R) == pytest.approx(FOLD_X)
    assert math.isnan(upper_branch(-FOLD_R - 1e-6))
    # Beyond it the only equilibrium is the lower branch, at about -2/sqrt(3) at the fold.
    assert lower_branch(-FOLD_R) == pytest.approx(-2.0 / math.sqrt(3.0))
    assert lower_branch(-FOLD_R - 1e-6) == pytest.approx(-2.0 / math.sqrt(3.0), abs=1e-3)
    assert upper_branch(-FOLD_R) - lower_branch(-FOLD_R) == pytest.approx(math.sqrt(3.0))
    # Ramping r up: the lower branch ends at +r_c and the system jumps to about +2/sqrt(3).
    assert lower_branch(FOLD_R) == pytest.approx(-FOLD_X)
    assert math.isnan(lower_branch(FOLD_R + 1e-6))
    assert upper_branch(FOLD_R) == pytest.approx(2.0 / math.sqrt(3.0))
    # Loop width: both branches coexist exactly for |r| <= r_c.
    r = np.linspace(-1.0, 1.0, 2001)
    both = (
        np.isfinite(upper_branch(r)) & np.isfinite(lower_branch(r)) & np.isfinite(middle_branch(r))
    )
    assert float(np.max(r[both]) - np.min(r[both])) == pytest.approx(2 * FOLD_R, abs=2e-3)


def test_branches_vectorised_match_scalar() -> None:
    r = np.array([-0.6, -FOLD_R, -0.1, 0.0, 0.3, FOLD_R, 0.8])
    for fn in (upper_branch, lower_branch, middle_branch):
        vec = fn(r)
        scalar = np.array([fn(float(v)) for v in r])
        np.testing.assert_allclose(vec, scalar, equal_nan=True)


def test_branches_agree_with_equilibria() -> None:
    for r in (-0.3, 0.0, 0.25):
        roots = equilibria(r)
        assert lower_branch(r) == pytest.approx(roots[0])
        assert middle_branch(r) == pytest.approx(roots[1])
        assert upper_branch(r) == pytest.approx(roots[2])


def test_drift_potential_growth_rate() -> None:
    x = np.linspace(-1.5, 1.5, 7)
    np.testing.assert_allclose(drift(x, 0.1), 0.1 + x - x**3)
    assert drift(1.0, 0.0) == 0.0
    assert growth_rate(0.0) == 1.0
    np.testing.assert_allclose(growth_rate(x), 1 - 3 * x**2)
    # f = -dV/dx (central finite difference) and V is lower in the valleys than on the hill.
    h = 1e-6
    for xi in (-0.7, 0.2, 1.1):
        dv = (potential(xi + h, 0.1) - potential(xi - h, 0.1)) / (2 * h)
        assert -dv == pytest.approx(drift(xi, 0.1), abs=1e-6)
    assert potential(1.0, 0.0) < potential(0.0, 0.0)
    # Broadcasting a scalar x against an array of r.
    assert potential(1.0, np.array([0.0, 0.5])).shape == (2,)


def test_growth_rate_is_derivative_of_drift() -> None:
    h = 1e-6
    for xi in (-1.0, 0.3, 0.9):
        df = (drift(xi + h, 0.0) - drift(xi - h, 0.0)) / (2 * h)
        assert growth_rate(xi) == pytest.approx(df, abs=1e-6)
