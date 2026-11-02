"""Tests of the Ornstein-Uhlenbeck theory."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tipping.theory import ou_acf, ou_ar1, ou_variance, predicted_indicators

SIGMA = 0.05
DT = 0.5

# (r, variance, AR(1)) for sigma = 0.05 and dt = 0.5 (hand-computed from the OU formulas).
REFERENCE = [
    (0.0, 0.000625, 0.3679),
    (-0.2, 0.00095, 0.5175),
    (-0.3, 0.00146, 0.6519),
    (-0.35, 0.00236, 0.7674),
    (-0.38, 0.00659, 0.9095),
]


@pytest.mark.parametrize(("r", "var", "ar1"), REFERENCE)
def test_predicted_indicators_reference_table(r: float, var: float, ar1: float) -> None:
    v, a = predicted_indicators(r, SIGMA, DT)
    assert v == pytest.approx(var, rel=1e-2)
    assert a == pytest.approx(ar1, abs=5e-5)


def test_ou_formulas() -> None:
    assert ou_variance(0.1, -2.0) == pytest.approx(0.01 / 4.0)
    assert ou_acf(-2.0, 0.0) == 1.0
    assert ou_acf(-2.0, 1.0) == pytest.approx(math.exp(-2.0))
    assert ou_acf(-2.0, -1.0) == pytest.approx(math.exp(-2.0))
    assert ou_ar1(-2.0, 0.5) == pytest.approx(math.exp(-1.0))
    assert ou_ar1(-2.0, 0.5) == ou_acf(-2.0, 0.5)


def test_ou_formulas_vectorised() -> None:
    lam = np.array([-2.0, -1.0, -0.5])
    np.testing.assert_allclose(ou_variance(SIGMA, lam), SIGMA**2 / (2 * np.abs(lam)))
    np.testing.assert_allclose(ou_ar1(lam, DT), np.exp(lam * DT))


def test_ou_marginal_and_unstable() -> None:
    assert ou_variance(SIGMA, 0.0) == math.inf
    assert ou_ar1(0.0, DT) == 1.0
    with pytest.raises(ValueError, match="growth_rate"):
        ou_variance(SIGMA, 0.5)
    with pytest.raises(ValueError, match="growth_rate"):
        ou_ar1(0.5, DT)


def test_predicted_indicators_grow_towards_fold() -> None:
    values = [predicted_indicators(r, SIGMA, DT) for r in (0.0, -0.1, -0.2, -0.3, -0.38)]
    variances, ar1s = zip(*values, strict=True)
    assert list(variances) == sorted(variances)
    assert list(ar1s) == sorted(ar1s)


def test_predicted_indicators_at_fold_and_beyond() -> None:
    variance, ar1 = predicted_indicators(-0.3849001794597505, SIGMA, DT)
    assert variance > 1e6
    assert ar1 == pytest.approx(1.0, abs=1e-6)
    with pytest.raises(ValueError, match="upper branch"):
        predicted_indicators(-0.5, SIGMA, DT)
