"""Compute every number quoted in the talk and write ``results/key_numbers.json``.

Single source of truth for the slides and the speech script: nothing is typed by hand.
Run with ``uv run python -m tipping.key_numbers`` after ``tipping sweep``.

Top-level keys of the JSON file:

``baseline``, ``sweep_summary``
    The baseline experiment (seed 42) and the seed-averaged sweep table.
``model``, ``protocol``
    Constants of the model (fold, jump, loop width) and of the analysis (windows, horizon).
``horizon``
    Baseline metrics when the analysis stops at 30, 40, 50 and 60 % of the ramp.
``tipping_vs_fold``
    When the noisy runs tip compared with the fold time, for several noise levels.
``window_vs_duration``
    Separate effects of the rolling-window length and of the ramp duration.
``a2_illustration``
    How representative the noisy-ball animation is (noise, ramp speed, selected seed).
``adiabaticity``
    Relaxation time against time left to the fold, for short and long ramps.
``sweep_paired``
    Per-seed comparison of the variance and AR(1) AUCs over the sweep cells.
``survivors``
    How many runs remain valid at high noise.
``detrend_control``
    A process whose mean moves but whose dynamics do not change, run through the same pipeline.
``ou_check``
    Simulated variance and AR(1) against the linear Ornstein-Uhlenbeck theory.
``matched_truncation``
    AUC when each control run is truncated at the same times as the ramp runs.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from tipping.config import ExperimentConfig, SimConfig, load_config
from tipping.evaluate import (
    Experiment,
    auc,
    bootstrap_ci,
    evaluate_pair,
    run_experiment,
    run_taus,
    tpr_at_fpr,
)
from tipping.indicators import compute_indicators, kendall_tau_per_run
from tipping.model import (
    FOLD_R,
    FOLD_X,
    growth_rate,
    lower_branch,
    middle_branch,
    potential,
    upper_branch,
)
from tipping.paths import default_config_path, results_dir
from tipping.simulate import Ramp, Trajectories, derive_seeds, first_crossing, simulate
from tipping.theory import predicted_indicators

FloatArray = NDArray[np.float64]

HORIZON_FRACTIONS: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6)
"""Fractions of the ramp at which the analysis stops."""

TIPPING_SIGMAS: tuple[float, ...] = (0.05, 0.10, 0.15)
"""Noise levels compared in :func:`tipping_vs_fold`."""

FOLD_LEAD_TIMES: tuple[float, ...] = (20.0, 30.0)
"""Times before the fold at which the escape barrier is evaluated."""

WindowSetting = tuple[float, int, int]
"""``(duration, window_samples, detrend_samples)`` of one run of :func:`window_vs_duration`."""

WINDOW_SETTINGS: tuple[WindowSetting, ...] = (
    (2000.0, 20, 5),
    (100.0, 20, 5),
    (100.0, 60, 15),
    (2000.0, 400, 100),
    (2000.0, 400, 25),
)
"""Same window on a long and a short ramp, a longer window on the short ramp, and the baseline."""

ADIABATICITY_DURATIONS: tuple[float, ...] = (100.0, 2000.0)
"""Ramp durations compared in :func:`adiabaticity`."""

HIGH_NOISE_SIGMAS: tuple[float, ...] = (0.15, 0.30)
"""Noise levels reported in :func:`survivors`."""

A2_BASELINE_DIP_LEVEL = 0.2
"""Level below which a run of the A2 illustration counts as a dip."""

OU_RATE = -2.0
"""Growth rate of the process used in :func:`detrend_control` (the rate at ``r = 0``)."""

OU_CHECK_CASES: tuple[tuple[float, float], ...] = (
    (0.0, 0.05),
    (-0.33, 0.015),
    (-0.33, 0.03),
    (-0.33, 0.05),
)
"""``(r, sigma)`` pairs compared with the linear theory in :func:`ou_check`."""


def _jsonable(value: Any) -> Any:
    """Convert NumPy scalars and arrays to JSON types, mapping non-finite floats to ``None``."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _fold_time(ramp: Trajectories) -> float:
    """Time of the first sample at which ``r`` has reached the fold ``-FOLD_R``."""
    return float(ramp.t[int(np.argmax(ramp.r <= -FOLD_R))])


def _tip_times(traj: Trajectories, threshold: float = 0.0) -> FloatArray:
    """First time each run is below ``threshold`` (``nan`` if it never is)."""
    index = first_crossing(traj.x, threshold)
    times = np.full(index.shape, np.nan)
    tipped = index < traj.n_samples
    times[tipped] = traj.t[index[tipped]]
    return times


def _rate(sim: SimConfig) -> float:
    """Speed ``|dr/dt|`` of the baseline ramp."""
    return abs(sim.r_end - sim.r_start) / sim.duration


def _baseline(cfg: ExperimentConfig, exp: Experiment) -> dict[str, Any]:
    res = exp.result
    x = exp.ramp.x  # (n_samples, n_runs)
    t = exp.ramp.t
    tipped = (x < 0).any(axis=0)
    first = np.argmax(x < 0, axis=0)
    tip_time = t[first[tipped]]
    out: dict[str, Any] = {
        "seed": cfg.sim.seed,
        "sigma": cfg.sim.sigma,
        "duration": cfg.sim.duration,
        "n_runs": cfg.sim.n_runs,
        "fold_r": FOLD_R,
        "fold_time": _fold_time(exp.ramp),
        "median_tip_time": float(np.median(tip_time)),
        "frac_ramp_tipped_ever": float(tipped.mean()),
        "auc_ar1": res.auc_ar1,
        "auc_var": res.auc_var,
        "tpr_ar1": res.tpr_ar1,
        "tpr_var": res.tpr_var,
        "frac_ramp_tipped_early": res.frac_ramp_tipped_early,
        "frac_null_tipped": res.frac_null_tipped,
        "n_valid_ramp": res.n_valid_ramp,
        "n_valid_null": res.n_valid_null,
        "median_tau_ramp_ar1": float(np.median(res.tau_ramp_ar1)),
        "median_tau_ramp_var": float(np.median(res.tau_ramp_var)),
        "median_tau_null_ar1": float(np.median(res.tau_null_ar1)),
        "median_tau_null_var": float(np.median(res.tau_null_var)),
        "tau_ar1_fpr5_threshold": float(np.quantile(res.tau_null_ar1, 0.95)),
    }
    lo, hi = bootstrap_ci(res.tau_ramp_ar1, res.tau_null_ar1, seed=0)
    out["auc_ar1_ci95"] = [lo, hi]
    lo, hi = bootstrap_ci(res.tau_ramp_var, res.tau_null_var, seed=0)
    out["auc_var_ci95"] = [lo, hi]
    lo, hi = bootstrap_ci(res.tau_ramp_ar1, res.tau_null_ar1, statistic=tpr_at_fpr, seed=0)
    out["tpr_ar1_ci95"] = [lo, hi]
    return out


def _sweep(summary: pd.DataFrame) -> dict[str, Any]:
    return {"columns": list(summary.columns), "rows": json.loads(summary.to_json(orient="records"))}


def model_constants() -> dict[str, float]:
    """Constants of the model quoted in the talk.

    Returns
    -------
    dict of str to float
        Fold position ``fold_r`` and ``fold_x``, the lower stable root at the fold, the jump
        size and the hysteresis-loop width ``2 * fold_r``.
    """
    lower = float(lower_branch(-FOLD_R))
    return {
        "fold_r": FOLD_R,
        "fold_x": FOLD_X,
        "lower_branch_at_fold": lower,
        "jump": FOLD_X - lower,
        "loop_width": 2.0 * FOLD_R,
    }


def protocol(cfg: ExperimentConfig) -> dict[str, float]:
    """Analysis settings of the baseline experiment expressed in time units.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration.

    Returns
    -------
    dict of str to float
        Sampling interval, rolling and detrending windows (samples and time), analysis horizon
        (fraction, time, value of ``r``), ramp speed and the value of ``r`` at the analysis end.
    """
    sim, ind = cfg.sim, cfg.indicators
    dt_sample = sim.dt * sim.sample_every
    t_end = ind.analysis_fraction * sim.duration
    return {
        "sample_interval": dt_sample,
        "window_samples": ind.window,
        "window_time": ind.window * dt_sample,
        "detrend_samples": ind.detrend_window,
        "detrend_time": ind.detrend_window * dt_sample,
        "analysis_fraction": ind.analysis_fraction,
        "analysis_end_time": t_end,
        "analysis_end_r": float(sim.ramp().r_at(t_end)),
        "ramp_rate": _rate(sim),
        "tip_margin_time": ind.detrend_window * dt_sample,
    }


def horizon_dependence(
    cfg: ExperimentConfig,
    exp: Experiment,
    fractions: Sequence[float] = HORIZON_FRACTIONS,
) -> dict[str, Any]:
    """Re-evaluate the baseline trajectories with the analysis stopping earlier.

    Only ``analysis_fraction`` changes; the simulated runs, windows and detrending are those of
    the baseline.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration.
    exp : Experiment
        Baseline experiment (ramp and control trajectories).
    fractions : sequence of float, optional
        Fractions of the ramp at which the analysis ends.

    Returns
    -------
    dict
        ``fold_time``, the fold position as a fraction of the ramp and one row per fraction with
        the analysis end time, the value of ``r`` there, the time left to the fold and the AUC
        and TPR of both indicators.
    """
    fold_time = _fold_time(exp.ramp)
    rows: list[dict[str, Any]] = []
    for fraction in fractions:
        indicators = cfg.indicators.model_copy(update={"analysis_fraction": fraction})
        res = evaluate_pair(exp.ramp, exp.null, indicators)
        t_end = fraction * cfg.sim.duration
        rows.append(
            {
                "analysis_fraction": fraction,
                "t_end": t_end,
                "r_end": float(cfg.sim.ramp().r_at(t_end)),
                "time_before_fold": fold_time - t_end,
                "auc_var": res.auc_var,
                "auc_ar1": res.auc_ar1,
                "tpr_var": res.tpr_var,
                "tpr_ar1": res.tpr_ar1,
                "n_valid_ramp": res.n_valid_ramp,
                "n_valid_null": res.n_valid_null,
            }
        )
    return {
        "seed": cfg.sim.seed,
        "fold_time": fold_time,
        "fold_fraction_of_ramp": fold_time / cfg.sim.duration,
        "rows": rows,
    }


def escape_barrier(r: float) -> float:
    """Height of the potential barrier that confines the upper stable state at ``r``.

    Parameters
    ----------
    r : float
        Control parameter, with ``-FOLD_R < r < FOLD_R``.

    Returns
    -------
    float
        ``V(unstable root) - V(upper stable root)``.
    """
    return float(potential(middle_branch(r), r) - potential(upper_branch(r), r))


def tipping_vs_fold(
    cfg: ExperimentConfig,
    exp: Experiment,
    sigmas: Sequence[float] = TIPPING_SIGMAS,
    lead_times: Sequence[float] = FOLD_LEAD_TIMES,
) -> dict[str, Any]:
    """Compare the time at which runs tip with the time at which the fold is crossed.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration (ramp, number of runs, seed).
    exp : Experiment
        Baseline experiment; its ramp group gives the baseline tip-time distribution.
    sigmas : sequence of float, optional
        Noise levels simulated again with the baseline ramp and the baseline ramp seed.
    lead_times : sequence of float, optional
        Times before the fold at which the escape barrier is evaluated.

    Returns
    -------
    dict
        ``baseline`` (fraction of ramp runs that tip before the fold time and the 5, 25, 50, 75
        and 95 percentiles of the tip time), ``deterministic_tip_time`` (noise-free run), its
        delay after the fold and the advance caused by noise, ``barrier`` (escape barrier and
        ``sigma**2 / 2`` at each lead time) and ``by_sigma`` (median tip time, median ``r`` at the
        tip, fraction of runs that tip before the fold).
    """
    sim = cfg.sim
    ramp = sim.ramp()
    fold_time = _fold_time(exp.ramp)
    tip = _tip_times(exp.ramp)
    tipped = np.isfinite(tip)
    percentiles = np.nanpercentile(tip, [5, 25, 50, 75, 95]) if tipped.any() else [np.nan] * 5

    clean = simulate(ramp, 0.0, 1, sim.dt, sim.sample_every, sim.x0, sim.seed)
    det_tip = float(_tip_times(clean)[0])

    ramp_seed = derive_seeds(sim.seed)[0]
    by_sigma: list[dict[str, Any]] = []
    for sigma in sigmas:
        traj = simulate(ramp, sigma, sim.n_runs, sim.dt, sim.sample_every, sim.x0, ramp_seed)
        times = _tip_times(traj)
        ok = np.isfinite(times)
        r_tip = np.asarray(ramp.r_at(times[ok]))
        by_sigma.append(
            {
                "sigma": sigma,
                "frac_tipped_ever": float(ok.mean()),
                "frac_tip_before_fold": float(np.mean(ok & (times < fold_time))),
                "median_tip_time": float(np.median(times[ok])) if ok.any() else None,
                "median_r_at_tip": float(np.median(r_tip)) if ok.any() else None,
                "r_at_tip_p10": float(np.percentile(r_tip, 10)) if ok.any() else None,
                "r_at_tip_p90": float(np.percentile(r_tip, 90)) if ok.any() else None,
            }
        )

    rate = _rate(sim)
    barrier = [
        {
            "time_before_fold": lead,
            "r": -FOLD_R + rate * lead,
            "barrier": escape_barrier(-FOLD_R + rate * lead),
            "noise_energy": sim.sigma**2 / 2.0,
        }
        for lead in lead_times
    ]
    median_tip = float(percentiles[2])
    return {
        "fold_time": fold_time,
        "baseline": {
            "sigma": sim.sigma,
            "frac_tipped_ever": float(tipped.mean()),
            "frac_tip_before_fold": float(np.mean(tipped & (tip < fold_time))),
            "tip_time_p5": float(percentiles[0]),
            "tip_time_p25": float(percentiles[1]),
            "tip_time_median": median_tip,
            "tip_time_p75": float(percentiles[3]),
            "tip_time_p95": float(percentiles[4]),
            "median_advance_before_fold": fold_time - median_tip,
        },
        "deterministic_tip_time": det_tip,
        "deterministic_delay_after_fold": det_tip - fold_time,
        "noise_advance_vs_deterministic": det_tip - median_tip,
        "barrier": barrier,
        "by_sigma": by_sigma,
    }


def window_vs_duration(
    cfg: ExperimentConfig,
    settings: Sequence[WindowSetting] = WINDOW_SETTINGS,
    seed: int = 11,
    n_runs: int | None = None,
) -> dict[str, Any]:
    """Separate the effect of the rolling window from that of the ramp duration.

    Each setting runs a fresh ramp-versus-control experiment with the baseline noise, the same
    seed and the given duration, rolling window and detrending window.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration (noise, ramp limits, analysis horizon).
    settings : sequence of tuple, optional
        ``(duration, window_samples, detrend_samples)`` triples.
    seed : int, optional
        Master seed shared by all settings.
    n_runs : int, optional
        Runs per group; defaults to the baseline value.

    Returns
    -------
    dict
        ``seed`` and one row per setting with the window in samples and time units and the AUC
        and TPR of both indicators.
    """
    interval = cfg.sim.dt * cfg.sim.sample_every
    rows: list[dict[str, Any]] = []
    for duration, window, detrend in settings:
        sim = cfg.sim.model_copy(
            update={
                "duration": duration,
                "seed": seed,
                "n_runs": cfg.sim.n_runs if n_runs is None else n_runs,
            }
        )
        indicators = cfg.indicators.model_copy(update={"window": window, "detrend_window": detrend})
        res = run_experiment(sim, indicators).result
        rows.append(
            {
                "duration": duration,
                "window_samples": window,
                "window_time": window * interval,
                "detrend_samples": detrend,
                "detrend_time": detrend * interval,
                "auc_var": res.auc_var,
                "auc_ar1": res.auc_ar1,
                "tpr_var": res.tpr_var,
                "tpr_ar1": res.tpr_ar1,
                "n_valid_ramp": res.n_valid_ramp,
                "n_valid_null": res.n_valid_null,
            }
        )
    return {"sigma": cfg.sim.sigma, "seed": seed, "rows": rows}


def a2_illustration(cfg: ExperimentConfig, n_seeds: int = 300) -> dict[str, Any]:
    """Quantify how representative the noisy-ball animation (A2) is.

    The noise, ramp and selected seed are read from :mod:`tipping.viz.animations`, and the
    realizations are produced by the same function that draws the clip.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration (noise and ramp speed to compare with).
    n_seeds : int, optional
        Number of seeds simulated at each noise level.

    Returns
    -------
    dict
        The animation constants, its noise and ramp speed relative to the baseline, the minimum
        of the selected realization and, for the animation noise and the baseline noise, the
        fraction of seeds that tip (``x < 0``) or dip below ``A2_BASELINE_DIP_LEVEL``.
    """
    from tipping.viz import animations

    chosen = animations.noisy_ball_realization()
    ramp_duration = float(chosen.t[-1])
    a2_rate = abs(animations.A2_R_END) / ramp_duration

    def fractions(sigma: float) -> dict[str, float]:
        minima = np.array(
            [
                float(np.min(animations.noisy_ball_realization(sigma=sigma, seed=seed).x))
                for seed in range(n_seeds)
            ]
        )
        return {
            "sigma": sigma,
            "frac_tip": float(np.mean(minima < 0.0)),
            "frac_dip_below_0p2": float(np.mean(minima < A2_BASELINE_DIP_LEVEL)),
        }

    return {
        "sigma": animations.A2_SIGMA,
        "seed": animations.A2_SEED,
        "r_end": animations.A2_R_END,
        "min_x_threshold": animations.A2_MIN_X,
        "ramp_duration": ramp_duration,
        "sigma_ratio_vs_baseline": animations.A2_SIGMA / cfg.sim.sigma,
        "rate_ratio_vs_baseline": a2_rate / _rate(cfg.sim),
        "duration_ratio_vs_baseline": cfg.sim.duration / ramp_duration,
        "selected_min_x": float(np.min(chosen.x)),
        "n_seeds": n_seeds,
        "at_animation_sigma": fractions(animations.A2_SIGMA),
        "at_baseline_sigma": fractions(cfg.sim.sigma),
    }


def _breakdown_lead_time(rate: float) -> float:
    """Time before the fold at which the relaxation time equals the time left to the fold.

    Solves ``1 / |lambda(r)| = (r + FOLD_R) / rate`` for ``r`` by bisection and returns
    ``(r + FOLD_R) / rate``.
    """

    def gap(r: float) -> float:
        return (r + FOLD_R) / rate - 1.0 / abs(float(growth_rate(upper_branch(r))))

    lo, hi = -FOLD_R + 1e-12, 0.0  # gap < 0 at the fold, > 0 far from it
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gap(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return (0.5 * (lo + hi) + FOLD_R) / rate


def adiabaticity(
    cfg: ExperimentConfig, durations: Sequence[float] = ADIABATICITY_DURATIONS
) -> dict[str, Any]:
    """Compare the relaxation time with the time left to the fold at the end of the analysis.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration (ramp limits and analysis horizon).
    durations : sequence of float, optional
        Ramp durations compared.

    Returns
    -------
    dict
        Relaxation time at ``r = 0``, and for each duration the ramp speed, the value of ``r`` at
        the analysis end, the relaxation time ``1 / |lambda|`` there, the time left to the fold
        and their ratio; ``breakdown_lead_time_baseline`` is the time before the fold at which
        the baseline ramp stops being adiabatic (relaxation time equal to time left).
    """
    rows: list[dict[str, Any]] = []
    for duration in durations:
        sim = cfg.sim.model_copy(update={"duration": duration})
        rate = _rate(sim)
        r_end = float(sim.ramp().r_at(cfg.indicators.analysis_fraction * duration))
        relaxation = 1.0 / abs(float(growth_rate(upper_branch(r_end))))
        left = (r_end + FOLD_R) / rate
        rows.append(
            {
                "duration": duration,
                "ramp_rate": rate,
                "r_analysis_end": r_end,
                "relaxation_time": relaxation,
                "time_to_fold": left,
                "ratio_relaxation_to_time_left": relaxation / left,
            }
        )
    return {
        "relaxation_time_r0": 1.0 / abs(float(growth_rate(upper_branch(0.0)))),
        "breakdown_lead_time_baseline": _breakdown_lead_time(_rate(cfg.sim)),
        "rows": rows,
    }


def sweep_paired(sweep: pd.DataFrame) -> dict[str, Any]:
    """Compare the variance and AR(1) metrics seed by seed within each sweep cell.

    Parameters
    ----------
    sweep : pandas.DataFrame
        Per-seed sweep table (``sigma``, ``duration``, ``seed``, ``auc_var``, ``auc_ar1``,
        ``tpr_var``, ``tpr_ar1``).

    Returns
    -------
    dict
        ``n_cells`` and, for the AUC and for the TPR, the number of cells where the variance
        beats AR(1) in all seeds, in some seeds and in none; ``auc_exceptions`` lists the cells
        where it does not win in every seed.
    """
    groups = sweep.groupby(["sigma", "duration"])
    out: dict[str, Any] = {"n_cells": len(groups), "n_seeds": int(sweep["seed"].nunique())}
    for metric in ("auc", "tpr"):
        wins = (sweep[f"{metric}_var"] > sweep[f"{metric}_ar1"]).groupby(
            [sweep["sigma"], sweep["duration"]]
        )
        count = wins.sum()
        size = wins.size()
        out[f"{metric}_variance_wins"] = {
            "all_seeds": int((count == size).sum()),
            "some_seeds": int(((count > 0) & (count < size)).sum()),
            "no_seed": int((count == 0).sum()),
        }
        if metric == "auc":
            out["auc_exceptions"] = [
                {
                    "sigma": float(sigma),
                    "duration": float(duration),
                    "seeds_variance_wins": int(count.loc[(sigma, duration)]),
                    "n_seeds": int(size.loc[(sigma, duration)]),
                }
                for sigma, duration in count.index[count < size]
            ]
    return out


def survivors(summary: pd.DataFrame, sigmas: Sequence[float] = HIGH_NOISE_SIGMAS) -> dict[str, Any]:
    """Tabulate how many runs stay valid for the analysis at high noise.

    Parameters
    ----------
    summary : pandas.DataFrame
        Seed-averaged sweep table.
    sigmas : sequence of float, optional
        Noise levels to report.

    Returns
    -------
    dict
        One row per noise level and duration with the mean number of valid ramp and control
        runs (out of the runs per group), the fractions that tipped and the mean AUCs.
    """
    rows: list[dict[str, Any]] = []
    for sigma in sigmas:
        part = summary[np.isclose(summary["sigma"], sigma)].sort_values("duration")
        rows.extend(
            {
                "sigma": float(sigma),
                "duration": float(rec["duration"]),
                "n_valid_ramp": float(rec["n_valid_ramp"]),
                "n_valid_null": float(rec["n_valid_null"]),
                "frac_ramp_tipped_early": float(rec["frac_ramp_tipped_early"]),
                "frac_null_tipped": float(rec["frac_null_tipped"]),
                "auc_var_mean": float(rec["auc_var_mean"]),
                "auc_ar1_mean": float(rec["auc_ar1_mean"]),
            }
            for rec in part.to_dict(orient="records")
        )
    return {"rows": rows}


def _simulate_ou(
    target: FloatArray, rate: float, sim: SimConfig, n_runs: int, seed: int
) -> FloatArray:
    """Euler-Maruyama paths of ``dy = rate (y - target(t)) dt + sigma dW``.

    ``target`` holds the moving mean at every integration step; the output is sampled like
    :func:`tipping.simulate.simulate`.
    """
    rng = np.random.default_rng(seed)
    n_steps = target.shape[0]
    n_blocks = n_steps // sim.sample_every
    out = np.empty((n_blocks + 1, n_runs))
    y = np.full(n_runs, sim.x0)
    out[0] = y
    amplitude = sim.sigma * math.sqrt(sim.dt)
    step = 0
    for block in range(n_blocks):
        noise = rng.standard_normal((sim.sample_every, n_runs)) * amplitude
        for i in range(sim.sample_every):
            y = y + rate * (y - target[step]) * sim.dt + noise[i]
            step += 1
        out[block + 1] = y
    return out


def detrend_control(
    cfg: ExperimentConfig, n_runs: int | None = None, seeds: tuple[int, int] = (1, 2)
) -> dict[str, Any]:
    """Check that the moving-average detrending does not create the early-warning signal.

    A process with constant recovery rate ``OU_RATE`` whose mean follows the baseline upper
    branch along the baseline ramp (so it moves, but its dynamics do not slow down) is compared
    with the same process at a fixed mean, through the same pipeline.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration.
    n_runs : int, optional
        Runs per group; defaults to the baseline value.
    seeds : tuple of int, optional
        Seeds of the moving-mean and of the fixed-mean groups.

    Returns
    -------
    dict
        AUC of the moving-mean group against the fixed-mean group for the variance and AR(1)
        indicators, their median taus, and the start and end of the moving mean.
    """
    sim = cfg.sim.model_copy(update={"n_runs": cfg.sim.n_runs if n_runs is None else n_runs})
    n_steps = round(sim.duration / sim.dt)
    t = np.arange(n_steps, dtype=np.float64) * sim.dt
    r = np.asarray(sim.ramp().r_at(t))
    moving = np.asarray(upper_branch(np.maximum(r, -FOLD_R)))
    fixed = np.full(n_steps, sim.x0)
    moved = run_taus(_simulate_ou(moving, OU_RATE, sim, sim.n_runs, seeds[0]), cfg.indicators)
    static = run_taus(_simulate_ou(fixed, OU_RATE, sim, sim.n_runs, seeds[1]), cfg.indicators)

    def finite(values: FloatArray) -> FloatArray:
        return values[np.isfinite(values)]

    out: dict[str, Any] = {
        "rate": OU_RATE,
        "mean_start": float(moving[0]),
        "mean_at_analysis_end": float(
            moving[round(cfg.indicators.analysis_fraction * n_steps) - 1]
        ),
        "mean_end": float(moving[-1]),
        "n_runs": sim.n_runs,
    }
    for name, a, b in (
        ("variance", moved.tau_var, static.tau_var),
        ("ar1", moved.tau_ar1, static.tau_ar1),
    ):
        a, b = finite(a), finite(b)
        out[name] = {
            "auc": auc(a, b) if a.size and b.size else None,
            "median_tau_moving": float(np.median(a)) if a.size else None,
            "median_tau_fixed": float(np.median(b)) if b.size else None,
        }
    return out


def ou_check(
    cfg: ExperimentConfig,
    n_runs: int = 300,
    duration: float = 1000.0,
    seed: int = 21,
    cases: Sequence[tuple[float, float]] = OU_CHECK_CASES,
) -> dict[str, Any]:
    """Compare simulated variance and AR(1) with the linear Ornstein-Uhlenbeck theory.

    Runs at constant ``r`` start on the upper branch; the first 100 samples are discarded and
    only the runs that never tip are used.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration (step and sampling interval).
    n_runs : int, optional
        Runs per case.
    duration : float, optional
        Simulated time per run.
    seed : int, optional
        Seed shared by all cases.
    cases : sequence of tuple, optional
        ``(r, sigma)`` pairs.

    Returns
    -------
    dict
        One row per case with the fraction of runs kept, the simulated and theoretical variance
        and AR(1), and the variance ratio.
    """
    sim = cfg.sim
    interval = sim.dt * sim.sample_every
    rows: list[dict[str, Any]] = []
    for r, sigma in cases:
        traj = simulate(
            Ramp.constant(r, duration), sigma, n_runs, sim.dt, sim.sample_every,
            float(upper_branch(r)), seed,
        )  # fmt: skip
        kept = first_crossing(traj.x) >= traj.n_samples
        x = traj.x[100:, kept]
        centred = x - x.mean(axis=0)
        variance = float(centred.var(axis=0).mean())
        head, tail = centred[:-1], centred[1:]
        corr = (head * tail).sum(axis=0) / np.sqrt((head**2).sum(axis=0) * (tail**2).sum(axis=0))
        var_theory, ar1_theory = predicted_indicators(r, sigma, interval)
        rows.append(
            {
                "r": r,
                "sigma": sigma,
                "frac_runs_kept": float(kept.mean()),
                "variance_sim": variance,
                "variance_theory": var_theory,
                "variance_ratio": variance / var_theory,
                "ar1_sim": float(corr.mean()),
                "ar1_theory": ar1_theory,
            }
        )
    return {"seed": seed, "n_runs": n_runs, "duration": duration, "rows": rows}


def matched_truncation(
    cfg: ExperimentConfig, sigmas: Sequence[float] = TIPPING_SIGMAS, seed: int = 9
) -> dict[str, Any]:
    """Check that truncating ramp runs at their tip does not bias the AUC.

    The control runs are truncated at stop indices drawn from those of the valid ramp runs (and
    never beyond their own tip), instead of at the common analysis horizon.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration.
    sigmas : sequence of float, optional
        Noise levels compared.
    seed : int, optional
        Master seed of the ramp and control groups.

    Returns
    -------
    dict
        Per noise level, the AUC of both indicators with the standard control and with the
        matched-truncation control, and the largest absolute difference over all levels.
    """
    sim_cfg, ind = cfg.sim, cfg.indicators
    ramp_seed, null_seed = derive_seeds(seed)
    rows: list[dict[str, Any]] = []
    for sigma in sigmas:
        args = (sigma, sim_cfg.n_runs, sim_cfg.dt, sim_cfg.sample_every, sim_cfg.x0)
        ramp = simulate(sim_cfg.ramp(), *args, ramp_seed)
        null = simulate(sim_cfg.control(), *args, null_seed)
        ramp_taus, null_taus = run_taus(ramp.x, ind), run_taus(null.x, ind)
        valid = np.isfinite(ramp_taus.tau_var) & np.isfinite(ramp_taus.tau_ar1)
        row: dict[str, Any] = {"sigma": sigma}
        if valid.any():
            horizon = round(ind.analysis_fraction * ramp.n_samples)
            stop_ramp = np.minimum(ramp_taus.tip_index - ind.detrend_window, horizon)
            stops = np.random.default_rng(0).choice(stop_ramp[valid], size=null.n_runs)
            stops = np.minimum(stops, null_taus.tip_index - ind.detrend_window)
            null_ind = compute_indicators(null.x, ind.window, ind.detrend_window)
            step = ind.resolved_step()
            matched = {
                "variance": kendall_tau_per_run(
                    null_ind.variance, ind.window, stops, step, ind.min_points
                ),
                "ar1": kendall_tau_per_run(null_ind.ar1, ind.window, stops, step, ind.min_points),
            }
            standard = {"variance": null_taus.tau_var, "ar1": null_taus.tau_ar1}
            pos = {"variance": ramp_taus.tau_var[valid], "ar1": ramp_taus.tau_ar1[valid]}
            for name in ("variance", "ar1"):
                for label, neg in (("standard", standard[name]), ("matched", matched[name])):
                    finite = neg[np.isfinite(neg)]
                    row[f"auc_{name}_{label}"] = auc(pos[name], finite) if finite.size else None
        rows.append(row)
    diffs = [
        abs(row[f"auc_{name}_standard"] - row[f"auc_{name}_matched"])
        for row in rows
        for name in ("variance", "ar1")
        if row.get(f"auc_{name}_standard") is not None
        and row.get(f"auc_{name}_matched") is not None
    ]
    return {"seed": seed, "rows": rows, "max_abs_auc_difference": max(diffs) if diffs else None}


def compute_key_numbers(
    cfg: ExperimentConfig,
    sweep: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    a2_seeds: int = 300,
    window_runs: int | None = None,
    window_settings: Sequence[WindowSetting] = WINDOW_SETTINGS,
    adiabaticity_durations: Sequence[float] = ADIABATICITY_DURATIONS,
    ou_runs: int = 300,
) -> dict[str, Any]:
    """Compute every key number from the configuration and the sweep tables.

    Parameters
    ----------
    cfg : ExperimentConfig
        Baseline configuration.
    sweep : pandas.DataFrame
        Per-seed sweep table.
    summary : pandas.DataFrame
        Seed-averaged sweep table.
    a2_seeds : int, optional
        Number of seeds used for the A2 illustration.
    window_runs : int, optional
        Runs per group in :func:`window_vs_duration` and :func:`detrend_control`.
    window_settings : sequence of tuple, optional
        Settings of :func:`window_vs_duration`.
    adiabaticity_durations : sequence of float, optional
        Durations of :func:`adiabaticity`.
    ou_runs : int, optional
        Runs per case in :func:`ou_check`.

    Returns
    -------
    dict
        JSON-ready dictionary (non-finite floats replaced by ``None``).
    """
    exp = run_experiment(cfg.sim, cfg.indicators)
    data: dict[str, Any] = {
        "baseline": _baseline(cfg, exp),
        "sweep_summary": _sweep(summary),
        "model": model_constants(),
        "protocol": protocol(cfg),
        "horizon": horizon_dependence(cfg, exp),
        "tipping_vs_fold": tipping_vs_fold(cfg, exp),
        "window_vs_duration": window_vs_duration(cfg, window_settings, n_runs=window_runs),
        "a2_illustration": a2_illustration(cfg, a2_seeds),
        "adiabaticity": adiabaticity(cfg, adiabaticity_durations),
        "sweep_paired": sweep_paired(sweep),
        "survivors": survivors(summary),
        "detrend_control": detrend_control(cfg, window_runs),
        "ou_check": ou_check(cfg, n_runs=ou_runs),
        "matched_truncation": matched_truncation(cfg),
    }
    return _jsonable(data)  # type: ignore[no-any-return]


def main() -> None:
    """Write the JSON file and print a short summary."""
    cfg = load_config(default_config_path())
    sweep = pd.read_parquet(results_dir() / "sweep.parquet")
    summary = pd.read_parquet(results_dir() / "sweep_summary.parquet")
    data = compute_key_numbers(cfg, sweep, summary)
    path = results_dir() / "key_numbers.json"
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(data["baseline"], indent=2))
    print(list(data))
    print(f"written {path}")


if __name__ == "__main__":
    main()
