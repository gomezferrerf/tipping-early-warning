"""Evaluation of early-warning indicators: ROC-style metrics and ramp-versus-control comparison.

A *ramp* group (the control parameter moves towards the fold) is compared with a *null*
(control) group at constant parameter. For every run, Kendall's tau between an indicator and
time measures how steadily the indicator rises; the indicator is a useful early warning if tau
separates the two groups.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray
from scipy import stats

from tipping.config import IndicatorConfig, SimConfig
from tipping.indicators import Indicators, compute_indicators, kendall_tau_per_run
from tipping.simulate import Ramp, Trajectories, derive_seeds, first_crossing, simulate

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]
Statistic = Callable[[FloatArray, FloatArray], float]


def _finite(values: FloatArray) -> FloatArray:
    return np.asarray(values, dtype=np.float64)[np.isfinite(values)]


def _check_n_boot(n_boot: int) -> None:
    if n_boot < 1:
        msg = f"n_boot must be >= 1, got {n_boot!r}"
        raise ValueError(msg)


def auc(pos: FloatArray, neg: FloatArray) -> float:
    """Area under the ROC curve, ``P(pos > neg) + 0.5 P(pos == neg)``.

    Computed from ranks (Mann-Whitney U statistic), so ties count one half.

    Parameters
    ----------
    pos : numpy.ndarray
        Scores of the positive group (here: ramp runs).
    neg : numpy.ndarray
        Scores of the negative group (here: control runs).

    Returns
    -------
    float
        AUC in ``[0, 1]``; 0.5 means no discrimination. Non-finite scores are ignored.

    Raises
    ------
    ValueError
        If either group has no finite score.
    """
    p, n = _finite(pos), _finite(neg)
    if p.size == 0 or n.size == 0:
        msg = "both groups need at least one finite score"
        raise ValueError(msg)
    ranks = stats.rankdata(np.concatenate([p, n]))
    u = ranks[: p.size].sum() - p.size * (p.size + 1) / 2.0
    return float(u / (p.size * n.size))


def tpr_at_fpr(pos: FloatArray, neg: FloatArray, fpr: float = 0.05) -> float:
    """True-positive rate at a fixed false-positive rate.

    The alarm threshold is the ``1 - fpr`` quantile of the negative scores (the 95th percentile
    for ``fpr = 0.05``) and the TPR is the fraction of positive scores strictly above it.

    Parameters
    ----------
    pos : numpy.ndarray
        Scores of the positive group.
    neg : numpy.ndarray
        Scores of the negative group.
    fpr : float, default 0.05
        Target false-positive rate, in ``(0, 1)``.

    Returns
    -------
    float
        Fraction of positive scores above the threshold. Non-finite scores are ignored.

    Raises
    ------
    ValueError
        If ``fpr`` is outside ``(0, 1)`` or either group has no finite score.
    """
    if not 0.0 < fpr < 1.0:
        msg = f"fpr must be in (0, 1), got {fpr!r}"
        raise ValueError(msg)
    p, n = _finite(pos), _finite(neg)
    if p.size == 0 or n.size == 0:
        msg = "both groups need at least one finite score"
        raise ValueError(msg)
    threshold = float(np.quantile(n, 1.0 - fpr))
    return float(np.mean(p > threshold))


def bootstrap_ci(
    pos: FloatArray,
    neg: FloatArray,
    statistic: Statistic = auc,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval of a two-sample statistic, resampling runs.

    Each replicate resamples the positive and the negative runs independently with
    replacement and recomputes ``statistic``.

    Parameters
    ----------
    pos, neg : numpy.ndarray
        Scores of the two groups (non-finite values are dropped first).
    statistic : callable, default :func:`auc`
        Function ``(pos, neg) -> float``.
    n_boot : int, default 1000
        Number of bootstrap replicates.
    alpha : float, default 0.05
        Two-sided level; the interval spans the ``alpha/2`` and ``1 - alpha/2`` percentiles.
    seed : int, default 0
        Seed of the resampling generator (the result is deterministic given the seed).

    Returns
    -------
    tuple of float
        Lower and upper confidence limits.

    Raises
    ------
    ValueError
        If ``n_boot < 1`` or either group has no finite score.
    """
    _check_n_boot(n_boot)
    p, n = _finite(pos), _finite(neg)
    if p.size == 0 or n.size == 0:
        msg = "both groups need at least one finite score"
        raise ValueError(msg)
    rng = np.random.default_rng(seed)
    ip = rng.integers(0, p.size, size=(n_boot, p.size))
    in_ = rng.integers(0, n.size, size=(n_boot, n.size))
    reps = np.array([statistic(p[ip[b]], n[in_[b]]) for b in range(n_boot)])
    lo, hi = np.percentile(reps, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return float(lo), float(hi)


def bootstrap_mean_ci(
    values: FloatArray, n_boot: int = 1000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval of a mean (e.g. over seeds).

    Parameters
    ----------
    values : numpy.ndarray
        Sample values (non-finite values are dropped first).
    n_boot : int, default 1000
        Number of bootstrap replicates.
    alpha : float, default 0.05
        Two-sided level.
    seed : int, default 0
        Seed of the resampling generator.

    Returns
    -------
    tuple of float
        Lower and upper confidence limits of the mean.

    Raises
    ------
    ValueError
        If ``n_boot < 1`` or ``values`` has no finite entry.
    """
    _check_n_boot(n_boot)
    v = _finite(values)
    if v.size == 0:
        msg = "values must contain at least one finite entry"
        raise ValueError(msg)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(n_boot, v.size))].mean(axis=1)
    lo, hi = np.percentile(means, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return float(lo), float(hi)


class RunTaus(NamedTuple):
    """Per-run Kendall taus and tip indices returned by :func:`run_taus`.

    Attributes
    ----------
    tau_var, tau_ar1 : numpy.ndarray
        Kendall tau of the rolling variance / AR(1) versus time, shape ``(n_runs,)``; ``nan``
        for invalid runs.
    tip_index : numpy.ndarray
        First sample index with ``x < tip_threshold`` per run (``n_samples`` if none).
    """

    tau_var: FloatArray
    tau_ar1: FloatArray
    tip_index: IntArray


def analysis_horizon(n_samples: int, cfg: IndicatorConfig) -> int:
    """Exclusive end index of the analysed part of a trajectory: ``round(fraction * n_samples)``.

    Parameters
    ----------
    n_samples : int
        Samples per run.
    cfg : IndicatorConfig
        Supplies ``analysis_fraction``.

    Returns
    -------
    int
        Number of leading samples that may enter the analysis.
    """
    return round(cfg.analysis_fraction * n_samples)


def analysis_stop(tip: IntArray, n_samples: int, cfg: IndicatorConfig) -> IntArray:
    """Exclusive end index of the analysis of every run.

    The analysis of a run ends at ``min(tip - detrend_window, horizon)``: the horizon is
    :func:`analysis_horizon` and the margin of ``detrend_window`` samples keeps the centred
    detrending filter away from the jump. The result may be negative for runs that tip at once.

    Parameters
    ----------
    tip : numpy.ndarray
        First sample index with ``x < tip_threshold`` per run (``n_samples`` if none), as returned
        by :func:`tipping.simulate.first_crossing`.
    n_samples : int
        Samples per run.
    cfg : IndicatorConfig
        Supplies ``detrend_window`` and ``analysis_fraction``.

    Returns
    -------
    numpy.ndarray
        Exclusive stop index per run, shape ``(n_runs,)``.
    """
    stop: IntArray = np.minimum(tip - cfg.detrend_window, analysis_horizon(n_samples, cfg))
    return stop


def run_taus_with_indicators(x: FloatArray, cfg: IndicatorConfig) -> tuple[RunTaus, Indicators]:
    """Like :func:`run_taus`, but also return the rolling indicators that were computed.

    Parameters
    ----------
    x : numpy.ndarray
        States, shape ``(n_samples, n_runs)``, without NaN.
    cfg : IndicatorConfig
        Window, detrending and truncation settings.

    Returns
    -------
    tuple
        ``(RunTaus, Indicators)``; the indicators are those of ``x`` with the configured windows.
    """
    n_samples = x.shape[0]
    tip = first_crossing(x, cfg.tip_threshold)
    stop = analysis_stop(tip, n_samples, cfg)
    ind = compute_indicators(x, cfg.window, cfg.detrend_window)
    step = cfg.resolved_step()
    tau_var = kendall_tau_per_run(ind.variance, cfg.window, stop, step, cfg.min_points)
    tau_ar1 = kendall_tau_per_run(ind.ar1, cfg.window, stop, step, cfg.min_points)
    return RunTaus(tau_var=tau_var, tau_ar1=tau_ar1, tip_index=tip), ind


def run_taus(x: FloatArray, cfg: IndicatorConfig) -> RunTaus:
    """Kendall tau of both indicators versus time for every run.

    Per run, the analysis ends (exclusive) at :func:`analysis_stop`, i.e.
    ``min(tip_index - detrend_window, round(analysis_fraction * n_samples))``: the margin keeps
    the centred detrending filter away from the jump. The rolling indicators are subsampled
    from index ``window`` every ``cfg.resolved_step()`` samples; runs with fewer than
    ``cfg.min_points`` points are invalid (``nan``).

    Parameters
    ----------
    x : numpy.ndarray
        States, shape ``(n_samples, n_runs)``. Must be free of NaN (the rolling statistics use
        cumulative sums, so one NaN would contaminate every later window).
    cfg : IndicatorConfig
        Window, detrending and truncation settings.

    Returns
    -------
    RunTaus
        ``(tau_var, tau_ar1, tip_index)``.
    """
    return run_taus_with_indicators(x, cfg)[0]


@dataclass(frozen=True, eq=False)
class EvalResult:
    """Outcome of comparing a ramp group with a null (control) group.

    Attributes
    ----------
    auc_var, auc_ar1 : float
        AUC of Kendall tau (variance / AR(1)) for ramp versus control; ``nan`` if a group has
        no valid run.
    tpr_var, tpr_ar1 : float
        True-positive rate at the configured false-positive rate (default 5%).
    frac_ramp_tipped_early : float
        Fraction of *all* ramp runs that tipped before the analysis horizon
        (``round(analysis_fraction * n_samples)``), i.e. noise-induced tips before the signal had
        time to build.
    frac_null_tipped : float
        Fraction of *all* control runs that tipped at any time during the simulation (the control
        is not tip-free when the noise is large).
    n_valid_ramp, n_valid_null : int
        Runs with a valid tau for both indicators; only these enter the metrics.
    tau_ramp_var, tau_ramp_ar1, tau_null_var, tau_null_ar1 : numpy.ndarray
        Valid per-run taus of each group and indicator (invalid runs removed).
    """

    auc_var: float
    auc_ar1: float
    tpr_var: float
    tpr_ar1: float
    frac_ramp_tipped_early: float
    frac_null_tipped: float
    n_valid_ramp: int
    n_valid_null: int
    tau_ramp_var: FloatArray
    tau_ramp_ar1: FloatArray
    tau_null_var: FloatArray
    tau_null_ar1: FloatArray


def evaluate_pair(
    ramp_traj: Trajectories, null_traj: Trajectories, cfg: IndicatorConfig
) -> EvalResult:
    """Compare early-warning indicators between a ramp group and a null group.

    Each run is analysed up to just before it tips (see :func:`run_taus`); the per-run Kendall
    taus of rolling variance and rolling lag-1 autocorrelation form two samples whose separation
    is summarised by the AUC and by the TPR at a fixed FPR.

    Notes
    -----
    **Survivor bias.** Runs that tip early (by noise, before the fold) are truncated
    ``detrend_window`` samples before the tip, and are dropped as invalid when fewer than
    ``min_points`` indicator values remain. The metrics are therefore computed on the runs
    that survived long enough, and this selection flatters the indicators: in noisy regimes
    the AUC can look acceptable while most runs tipped with no usable warning. A high AUC says
    nothing about whether an alarm arrives before the tip. Always read the AUC together with
    ``frac_ramp_tipped_early``, ``frac_null_tipped`` and ``n_valid_ramp`` / ``n_valid_null``.

    Parameters
    ----------
    ramp_traj : Trajectories
        Runs with the control parameter approaching the fold.
    null_traj : Trajectories
        Control runs at constant parameter (same number of samples as ``ramp_traj``).
    cfg : IndicatorConfig
        Windows, truncation and metric settings.

    Returns
    -------
    EvalResult
        Metrics, tipped fractions and the per-run taus.

    Raises
    ------
    ValueError
        If the two groups have a different number of samples.
    """
    if ramp_traj.n_samples != null_traj.n_samples:
        msg = "ramp and null trajectories must have the same number of samples"
        raise ValueError(msg)
    n_samples = ramp_traj.n_samples
    horizon = analysis_horizon(n_samples, cfg)

    ramp = run_taus(ramp_traj.x, cfg)
    null = run_taus(null_traj.x, cfg)
    ramp_ok = np.isfinite(ramp.tau_var) & np.isfinite(ramp.tau_ar1)
    null_ok = np.isfinite(null.tau_var) & np.isfinite(null.tau_ar1)

    rv, ra = ramp.tau_var[ramp_ok], ramp.tau_ar1[ramp_ok]
    nv, na = null.tau_var[null_ok], null.tau_ar1[null_ok]
    comparable = rv.size > 0 and nv.size > 0
    nan = float("nan")
    return EvalResult(
        auc_var=auc(rv, nv) if comparable else nan,
        auc_ar1=auc(ra, na) if comparable else nan,
        tpr_var=tpr_at_fpr(rv, nv, cfg.fpr) if comparable else nan,
        tpr_ar1=tpr_at_fpr(ra, na, cfg.fpr) if comparable else nan,
        frac_ramp_tipped_early=float(np.mean(ramp.tip_index < horizon)),
        frac_null_tipped=float(np.mean(null.tip_index < n_samples)),
        n_valid_ramp=int(ramp_ok.sum()),
        n_valid_null=int(null_ok.sum()),
        tau_ramp_var=rv,
        tau_ramp_ar1=ra,
        tau_null_var=nv,
        tau_null_ar1=na,
    )


@dataclass(frozen=True, eq=False)
class Experiment:
    """A simulated ramp/control pair together with its evaluation.

    Attributes
    ----------
    ramp, null : Trajectories
        Simulated ramp and control groups.
    result : EvalResult
        Evaluation of the pair.
    """

    ramp: Trajectories
    null: Trajectories
    result: EvalResult


def run_experiment(
    sim: SimConfig, indicators: IndicatorConfig, seed: int | None = None
) -> Experiment:
    """Simulate a ramp group and a control group and evaluate the indicators.

    The ramp and control noise streams are independent: their seeds are derived from the master
    seed with :func:`tipping.simulate.derive_seeds`.

    Parameters
    ----------
    sim : SimConfig
        Simulation settings.
    indicators : IndicatorConfig
        Indicator and evaluation settings.
    seed : int, optional
        Master seed; defaults to ``sim.seed``.

    Returns
    -------
    Experiment
        Trajectories of both groups and the :class:`EvalResult`.
    """
    ramp_seed, null_seed = derive_seeds(sim.seed if seed is None else seed)

    def run(schedule: Ramp, group_seed: int) -> Trajectories:
        return simulate(
            schedule,
            sigma=sim.sigma,
            n_runs=sim.n_runs,
            dt=sim.dt,
            sample_every=sim.sample_every,
            x0=sim.x0,
            seed=group_seed,
        )

    ramp = run(sim.ramp(), ramp_seed)
    null = run(sim.control(), null_seed)
    return Experiment(ramp=ramp, null=null, result=evaluate_pair(ramp, null, indicators))
