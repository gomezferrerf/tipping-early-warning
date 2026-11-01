"""Tests of the Euler-Maruyama simulator."""

from __future__ import annotations

import numpy as np
import pytest

from tipping.model import FOLD_R
from tipping.simulate import Ramp, Trajectories, derive_seeds, first_crossing, simulate
from tipping.theory import predicted_indicators


def _run(
    ramp: Ramp,
    *,
    sigma: float = 0.05,
    n_runs: int = 10,
    dt: float = 0.01,
    sample_every: int = 50,
    x0: float = 1.0,
    seed: int = 1,
) -> Trajectories:
    return simulate(ramp, sigma, n_runs, dt, sample_every, x0, seed)


def test_ramp_r_at() -> None:
    ramp = Ramp(0.0, -0.6, 100.0)
    assert ramp.r_at(0.0) == 0.0
    assert ramp.r_at(50.0) == pytest.approx(-0.3)
    assert ramp.r_at(100.0) == pytest.approx(-0.6)
    assert ramp.r_at(250.0) == pytest.approx(-0.6)  # held after the ramp
    assert ramp.r_at(-5.0) == 0.0
    np.testing.assert_allclose(ramp.r_at(np.array([0.0, 25.0, 100.0])), [0.0, -0.15, -0.6])


def test_ramp_constant_and_validation() -> None:
    const = Ramp.constant(0.2, 10.0)
    assert const.r_start == const.r_end == 0.2
    assert const.r_at(7.0) == 0.2
    with pytest.raises(ValueError, match="duration"):
        Ramp(0.0, 1.0, 0.0)


def test_shapes_and_metadata() -> None:
    tr = _run(Ramp(0.0, -0.6, 100.0), n_runs=7)
    assert tr.x.shape == (201, 7)
    assert tr.t.shape == tr.r.shape == (201,)
    assert (tr.n_samples, tr.n_runs) == (201, 7)
    assert tr.t[0] == 0.0
    assert tr.t[-1] == pytest.approx(100.0)
    assert tr.sample_interval == pytest.approx(0.5)
    np.testing.assert_array_equal(tr.x[0], 1.0)
    assert tr.r[0] == 0.0
    assert tr.r[-1] == pytest.approx(-0.6)


def test_seed_reproducibility() -> None:
    ramp = Ramp(0.0, -0.3, 50.0)
    a, b = _run(ramp, seed=7), _run(ramp, seed=7)
    c = _run(ramp, seed=8)
    np.testing.assert_array_equal(a.x, b.x)
    assert not np.array_equal(a.x, c.x)


def test_stream_independent_of_sampling_interval() -> None:
    ramp = Ramp(0.0, -0.3, 20.0)
    fine = _run(ramp, sample_every=1, seed=3)
    coarse = _run(ramp, sample_every=5, seed=3)
    np.testing.assert_allclose(fine.x[::5], coarse.x, atol=1e-12)


def test_zero_noise_is_deterministic_and_stays_on_the_equilibrium() -> None:
    tr = _run(Ramp.constant(0.0, 50.0), sigma=0.0)
    np.testing.assert_allclose(tr.x, 1.0, atol=1e-12)
    relax = _run(Ramp.constant(0.0, 50.0), sigma=0.0, x0=0.5)
    assert relax.x[-1, 0] == pytest.approx(1.0, abs=1e-6)


def test_deterministic_ramp_follows_branch_until_the_fold() -> None:
    # sigma = 0: the ball stays on the upper branch until r = -r_c, then falls.
    tr = _run(Ramp(0.0, -0.6, 2000.0), sigma=0.0, n_runs=1)
    tipped = int(first_crossing(tr.x)[0])
    assert tipped < tr.n_samples
    assert tr.r[tipped] < -FOLD_R
    assert tr.r[tipped] > -0.5  # falls shortly after the fold, not at the end


def test_euler_maruyama_sqrt_dt_scaling() -> None:
    # One step from the equilibrium x = 1 at r = 0 (f = 0): x_1 - x_0 = sigma sqrt(dt) xi.
    sigma = 0.1
    for dt in (0.01, 0.04):
        tr = simulate(Ramp.constant(0.0, 1.0), sigma, 40_000, dt, 1, 1.0, seed=5)
        step = tr.x[1] - tr.x[0]
        assert abs(step.mean()) < 5 * sigma * np.sqrt(dt) / np.sqrt(40_000)
        assert step.std() == pytest.approx(sigma * np.sqrt(dt), rel=0.02)
    # Quadrupling dt doubles the standard deviation of the increment.


def test_stationary_variance_and_ar1_at_r0() -> None:
    sigma, dt, every = 0.05, 0.01, 50
    tr = simulate(Ramp.constant(0.0, 400.0), sigma, 200, dt, every, 1.0, seed=11)
    x = tr.x[20:]  # drop a short transient (x0 is already the equilibrium)
    var_theory, ar1_theory = predicted_indicators(0.0, sigma, dt * every)
    resid = x - x.mean(axis=0)
    var = float(np.mean(resid**2))
    ar1 = float(np.sum(resid[1:] * resid[:-1]) / np.sum(resid**2))
    assert var == pytest.approx(var_theory, rel=0.10)
    assert ar1 == pytest.approx(ar1_theory, abs=0.03)


def test_first_crossing() -> None:
    x = np.array([[1.0, 1.0, 1.0], [0.5, -0.1, 1.0], [-0.2, -0.3, 1.0], [-1.0, -1.0, 1.0]])
    np.testing.assert_array_equal(first_crossing(x), [2, 1, 4])
    np.testing.assert_array_equal(first_crossing(x, threshold=0.6), [1, 1, 4])
    assert first_crossing(x).dtype.kind == "i"


def test_invalid_arguments() -> None:
    ramp = Ramp.constant(0.0, 10.0)
    with pytest.raises(ValueError, match="sigma"):
        simulate(ramp, -1.0, 2, 0.01, 10, 1.0, 0)
    with pytest.raises(ValueError, match="n_runs"):
        simulate(ramp, 0.1, 0, 0.01, 10, 1.0, 0)
    with pytest.raises(ValueError, match="sampling interval"):
        simulate(Ramp.constant(0.0, 0.1), 0.1, 2, 0.01, 50, 1.0, 0)


def test_derive_seeds_are_distinct_and_deterministic() -> None:
    assert derive_seeds(42) == derive_seeds(42)
    first, second = derive_seeds(42)
    assert first != second
    assert derive_seeds(43) != derive_seeds(42)


def test_sigma_end_none_and_equal_sigma_are_bit_identical() -> None:
    ramp = Ramp(0.0, -0.3, 50.0)
    default = _run(ramp, seed=21)
    explicit_none = simulate(ramp, 0.05, 10, 0.01, 50, 1.0, 21, sigma_end=None)
    equal = simulate(ramp, 0.05, 10, 0.01, 50, 1.0, 21, sigma_end=0.05)
    np.testing.assert_array_equal(default.x, explicit_none.x)
    np.testing.assert_allclose(default.x, equal.x, rtol=0, atol=1e-12)
    assert default.sigma_end is None
    assert equal.sigma_end == 0.05


def test_increasing_noise_raises_variance_by_squared_ratio() -> None:
    sigma, sigma_end = 0.03, 0.06
    tr = simulate(
        Ramp.constant(0.0, 1000.0), sigma, 200, 0.01, 50, 1.0, seed=31, sigma_end=sigma_end
    )
    fifth = tr.n_samples // 5
    first = np.var(tr.x[:fifth] - 1.0)
    last = np.var(tr.x[-fifth:] - 1.0)
    # Variance tracks sigma(t)^2 (slowly varying); the mean ratio over the two fifths is
    # (mean sigma^2 in last fifth) / (mean sigma^2 in first fifth) = 3.4 for a 1 -> 2 ramp.
    t = tr.t
    amp2 = (sigma + (sigma_end - sigma) * t / t[-1]) ** 2
    expected = amp2[-fifth:].mean() / amp2[:fifth].mean()
    assert last > first
    assert last / first == pytest.approx(expected, rel=0.25)


def test_sigma_end_validation() -> None:
    with pytest.raises(ValueError, match="sigma_end"):
        simulate(Ramp.constant(0.0, 10.0), 0.1, 2, 0.01, 10, 1.0, 0, sigma_end=-0.1)
