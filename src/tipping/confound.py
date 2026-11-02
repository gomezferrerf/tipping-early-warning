"""Noise-amplitude confound: rising noise should fool the variance but not the AR(1).

Near a stable equilibrium the system behaves like an Ornstein-Uhlenbeck process with rate
``|lambda|``, whose stationary variance is ``sigma**2 / (2 |lambda|)`` while its sampled
lag-1 autocorrelation is ``exp(lambda * dt)``. Variance therefore depends on the noise amplitude
``sigma`` and the AR(1) does not, so a noise amplitude that grows while the system stays far from
the fold (``r`` constant) should raise a false alarm on the variance but not on the AR(1).

This module tests that prediction with the same machinery as the baseline experiment
(:func:`tipping.simulate.simulate`, :func:`tipping.evaluate.run_taus`, AUC and TPR at 5% FPR of
Kendall's tau versus time). Four kinds of groups are simulated per seed and compared:

``control``
    Constant ``r = 0`` and constant ``sigma``: the null of every scenario but one.
``fold``
    ``r`` falls from 0 to ``-0.6`` at constant ``sigma``: the baseline experiment, the positive
    control (both indicators should flag).
``noise_<s>``
    ``r = 0`` throughout while ``sigma`` rises linearly from ``sigma`` to ``s``: the confound
    (variance should flag, AR(1) should not).
``mixed_<s>``
    ``r`` falls to ``-0.6`` *and* ``sigma`` rises to ``s``.

A scenario is a (positive group, null group) pair. Besides each group against the control there
is ``mixed_vs_noise_<s>``: the mixed group against the noise-ramp group with the same ``s``,
i.e. "is the fold approach detectable when the noise is rising in both groups?".

Notes
-----
Nothing here assumes the outcome: the module reports what the simulation gives, including any
effect of the noise ramp on the AR(1) through the nonlinearity or the moving-average
detrending.
"""

from __future__ import annotations

import argparse
import json
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from tipping.config import IndicatorConfig, SimConfig, load_config
from tipping.evaluate import (
    RunTaus,
    analysis_horizon,
    analysis_stop,
    auc,
    bootstrap_ci,
    run_taus_with_indicators,
    tpr_at_fpr,
)
from tipping.indicators import compute_indicators
from tipping.io import write_parquet
from tipping.paths import default_config_path, results_dir
from tipping.simulate import Ramp, Trajectories, derive_seeds, first_crossing, simulate

FloatArray = NDArray[np.float64]

DEFAULT_SEEDS: tuple[int, ...] = (1, 2, 3)
DEFAULT_SIGMA_ENDS: tuple[float, ...] = (0.10, 0.15)
"""Final noise amplitudes (2x and 3x the baseline 0.05, i.e. 4x and 9x the variance).

The Kramers escape rate at ``r = 0`` is about ``exp(-2 dV / sigma**2)`` with barrier
``dV = 1/4``: ``exp(-22) ~ 3e-10`` per time unit at ``sigma = 0.15``, so the system stays in its
valley (the run counts the tipped fraction to confirm). Larger values would let the noise tip the
system and turn the experiment into a different one.
"""
RAMP_R_END = -0.6
"""Final control parameter of the ramp groups (``fold`` and ``mixed_<s>``), past the fold."""
POOLED_SEED = -1
"""Value of the ``seed`` column on the rows that pool all seeds."""

FRAME_COLUMNS: tuple[str, ...] = (
    "scenario",
    "pos_group",
    "null_group",
    "seed",
    "indicator",
    "n_runs",
    "sigma_start",
    "sigma_end",
    "r_end",
    "auc",
    "auc_ci_lo",
    "auc_ci_hi",
    "tpr",
    "tpr_ci_lo",
    "tpr_ci_hi",
    "median_tau_pos",
    "median_tau_null",
    "change_pos",
    "change_null",
    "frac_pos_tipped_early",
    "frac_null_tipped",
    "n_valid_pos",
    "n_valid_null",
)
"""Columns of the table returned by :func:`run_confound` (and of ``confound.parquet``)."""

INDICATORS: tuple[str, ...] = ("variance", "ar1")


@dataclass(frozen=True)
class Group:
    """One simulated group of runs.

    Attributes
    ----------
    name : str
        Group identifier (``"control"``, ``"fold"``, ``"noise_0.10"``, ...).
    r_end : float
        Final control parameter (``r`` starts at 0); ``0`` means ``r`` is constant.
    sigma_end : float or None
        Final noise amplitude; ``None`` keeps the noise constant.
    """

    name: str
    r_end: float
    sigma_end: float | None


@dataclass(frozen=True)
class Scenario:
    """A comparison of a positive group with a null group.

    Attributes
    ----------
    name : str
        Scenario identifier.
    pos : Group
        Group whose indicators are expected to rise.
    null : Group
        Reference group.
    """

    name: str
    pos: Group
    null: Group


def build_scenarios(
    sigma_ends: Sequence[float] = DEFAULT_SIGMA_ENDS, r_end: float = RAMP_R_END
) -> list[Scenario]:
    """Build the list of scenarios.

    Parameters
    ----------
    sigma_ends : sequence of float, default (0.10, 0.15)
        Final noise amplitudes of the noise-ramp and mixed groups.
    r_end : float, default :data:`RAMP_R_END`
        Final control parameter of the ``fold`` and ``mixed_<s>`` groups; :func:`run_confound`
        passes the ``r_end`` of the simulation settings, so the fold group always matches the
        baseline experiment.

    Returns
    -------
    list of Scenario
        ``fold``, then ``noise_<s>``, ``mixed_<s>`` and ``mixed_vs_noise_<s>`` for each ``s``.
    """
    control = Group("control", 0.0, None)
    scenarios = [Scenario("fold", Group("fold", r_end, None), control)]
    for s in sigma_ends:
        noise = Group(f"noise_{s:.2f}", 0.0, float(s))
        mixed = Group(f"mixed_{s:.2f}", r_end, float(s))
        scenarios.append(Scenario(noise.name, noise, control))
        scenarios.append(Scenario(mixed.name, mixed, control))
        scenarios.append(Scenario(f"mixed_vs_noise_{s:.2f}", mixed, noise))
    return scenarios


def group_seed(seed: int, group: Group) -> int:
    """Seed of a group's noise stream: a pure function of the master seed and the group name.

    The control group uses the same seed as the null group of
    :func:`tipping.evaluate.run_experiment` (``derive_seeds(seed)[1]``); the others hash the group
    name, so adding a scenario never changes the others.

    Parameters
    ----------
    seed : int
        Master seed.
    group : Group
        Group to simulate.

    Returns
    -------
    int
        Seed for :func:`tipping.simulate.simulate`.
    """
    if group.name == "control":
        return derive_seeds(seed)[1]
    key = zlib.crc32(group.name.encode())
    return int(np.random.SeedSequence([seed, key]).generate_state(1)[0])


def simulate_group(sim: SimConfig, group: Group, seed: int) -> Trajectories:
    """Simulate one group with the settings of ``sim``.

    ``r`` is a :class:`~tipping.simulate.Ramp` from ``sim.r_start`` to ``group.r_end`` (constant
    when both are 0, as for the control and noise groups with the default ``r_start = 0``) and
    the noise amplitude ramps from ``sim.sigma`` to ``group.sigma_end`` if that is given.

    Parameters
    ----------
    sim : SimConfig
        Time step, sampling, duration, initial state, base noise amplitude and ``n_runs``.
    group : Group
        Group to simulate.
    seed : int
        Master seed.

    Returns
    -------
    Trajectories
        Sampled runs of the group.
    """
    schedule = Ramp(sim.r_start, group.r_end, sim.duration)
    return simulate(
        schedule,
        sigma=sim.sigma,
        n_runs=sim.n_runs,
        dt=sim.dt,
        sample_every=sim.sample_every,
        x0=sim.x0,
        seed=group_seed(seed, group),
        sigma_end=group.sigma_end,
    )


@dataclass(frozen=True, eq=False)
class GroupStats:
    """Per-run indicator statistics of one group (all arrays have shape ``(n_runs,)``).

    Attributes
    ----------
    tau_var, tau_ar1 : numpy.ndarray
        Kendall tau versus time of the rolling variance / AR(1); ``nan`` for invalid runs.
    change_var : numpy.ndarray
        Ratio of the rolling variance at the last analysed sample to its first value.
    change_ar1 : numpy.ndarray
        Difference of the rolling AR(1) between the last analysed sample and its first value.
    valid : numpy.ndarray
        Runs with a finite tau for both indicators.
    n_tipped_early, n_tipped_ever, n_runs : int
        Runs that tipped before the analysis horizon, runs that tipped at any time, and all runs.
    """

    tau_var: FloatArray
    tau_ar1: FloatArray
    change_var: FloatArray
    change_ar1: FloatArray
    valid: NDArray[np.bool_]
    n_tipped_early: int
    n_tipped_ever: int
    n_runs: int


def group_stats(traj: Trajectories, cfg: IndicatorConfig) -> GroupStats:
    """Compute the per-run taus and the first-to-last change of both indicators.

    The taus come from :func:`tipping.evaluate.run_taus` (same truncation before a tip and same
    validity rule as the baseline); the change of each indicator is measured between index
    ``window`` (where the Kendall subsampling starts) and the last analysed sample of the run.

    Parameters
    ----------
    traj : Trajectories
        Simulated runs.
    cfg : IndicatorConfig
        Windows, truncation and metric settings.

    Returns
    -------
    GroupStats
        Taus, changes, validity mask and tipped counts.
    """
    taus: RunTaus
    taus, ind = run_taus_with_indicators(traj.x, cfg)
    n_samples = traj.n_samples
    horizon = analysis_horizon(n_samples, cfg)
    stop = analysis_stop(taus.tip_index, n_samples, cfg)
    valid = np.isfinite(taus.tau_var) & np.isfinite(taus.tau_ar1)
    cols = np.arange(traj.n_runs)
    last = np.clip(stop - 1, 0, n_samples - 1)
    first = min(cfg.window, n_samples - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        change_var = ind.variance[last, cols] / ind.variance[first]
    change_ar1 = ind.ar1[last, cols] - ind.ar1[first]
    change_var = np.where(valid, change_var, np.nan)
    change_ar1 = np.where(valid, change_ar1, np.nan)
    return GroupStats(
        tau_var=taus.tau_var,
        tau_ar1=taus.tau_ar1,
        change_var=change_var,
        change_ar1=change_ar1,
        valid=valid,
        n_tipped_early=int(np.sum(taus.tip_index < horizon)),
        n_tipped_ever=int(np.sum(taus.tip_index < n_samples)),
        n_runs=traj.n_runs,
    )


def _pool(stats: Sequence[GroupStats]) -> GroupStats:
    """Concatenate the runs of several :class:`GroupStats` (one per seed)."""
    return GroupStats(
        tau_var=np.concatenate([s.tau_var for s in stats]),
        tau_ar1=np.concatenate([s.tau_ar1 for s in stats]),
        change_var=np.concatenate([s.change_var for s in stats]),
        change_ar1=np.concatenate([s.change_ar1 for s in stats]),
        valid=np.concatenate([s.valid for s in stats]),
        n_tipped_early=sum(s.n_tipped_early for s in stats),
        n_tipped_ever=sum(s.n_tipped_ever for s in stats),
        n_runs=sum(s.n_runs for s in stats),
    )


def _median(values: FloatArray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if finite.size else float("nan")


def _rows(
    scenario: Scenario,
    seed: int,
    pos: GroupStats,
    null: GroupStats,
    sim: SimConfig,
    fpr: float,
    n_boot: int,
) -> list[dict[str, Any]]:
    """Metric rows (one per indicator) of one scenario and one seed (or the pooled seeds)."""
    scenario_key = zlib.crc32(scenario.name.encode())
    boot_seed = int(np.random.SeedSequence([abs(seed), scenario_key]).generate_state(1)[0])
    rows: list[dict[str, Any]] = []
    pv, pn = pos.valid, null.valid
    for indicator in INDICATORS:
        if indicator == "variance":
            tp, tn = pos.tau_var[pv], null.tau_var[pn]
            cp, cn = pos.change_var[pv], null.change_var[pn]
        else:
            tp, tn = pos.tau_ar1[pv], null.tau_ar1[pn]
            cp, cn = pos.change_ar1[pv], null.change_ar1[pn]
        comparable = tp.size > 0 and tn.size > 0
        nan = float("nan")

        def tpr(a: FloatArray, b: FloatArray) -> float:
            return tpr_at_fpr(a, b, fpr)

        a_lo, a_hi = bootstrap_ci(tp, tn, auc, n_boot, seed=boot_seed) if comparable else (nan, nan)
        t_lo, t_hi = bootstrap_ci(tp, tn, tpr, n_boot, seed=boot_seed) if comparable else (nan, nan)
        rows.append(
            {
                "scenario": scenario.name,
                "pos_group": scenario.pos.name,
                "null_group": scenario.null.name,
                "seed": seed,
                "indicator": indicator,
                "n_runs": pos.n_runs,
                "sigma_start": sim.sigma,
                "sigma_end": (
                    float("nan") if scenario.pos.sigma_end is None else scenario.pos.sigma_end
                ),
                "r_end": scenario.pos.r_end,
                "auc": auc(tp, tn) if comparable else nan,
                "auc_ci_lo": a_lo,
                "auc_ci_hi": a_hi,
                "tpr": tpr(tp, tn) if comparable else nan,
                "tpr_ci_lo": t_lo,
                "tpr_ci_hi": t_hi,
                "median_tau_pos": _median(tp),
                "median_tau_null": _median(tn),
                "change_pos": _median(cp),
                "change_null": _median(cn),
                "frac_pos_tipped_early": pos.n_tipped_early / pos.n_runs,
                "frac_null_tipped": null.n_tipped_ever / null.n_runs,
                "n_valid_pos": int(pv.sum()),
                "n_valid_null": int(pn.sum()),
            }
        )
    return rows


def default_configs(n_runs: int = 300) -> tuple[SimConfig, IndicatorConfig]:
    """Load the baseline simulation and indicator settings from ``configs/default.yaml``.

    Parameters
    ----------
    n_runs : int, default 300
        Runs per group.

    Returns
    -------
    tuple of (SimConfig, IndicatorConfig)
        Baseline settings with ``n_runs`` overridden.
    """
    base = load_config(default_config_path())
    return base.sim.model_copy(update={"n_runs": n_runs}), base.indicators


def run_confound(
    n_runs: int = 300,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    sigma_ends: Sequence[float] = DEFAULT_SIGMA_ENDS,
    *,
    sim: SimConfig | None = None,
    indicators: IndicatorConfig | None = None,
    n_boot: int = 1000,
) -> pd.DataFrame:
    """Run the noise-confound experiment.

    For every seed the control, fold, noise-ramp and mixed groups are simulated once and every
    scenario of :func:`build_scenarios` is evaluated: AUC and TPR at the configured FPR of
    Kendall's tau (variance and AR(1)) with percentile bootstrap 95% confidence intervals that
    resample runs, median tau per group and the median first-to-last change of each indicator.
    Rows with ``seed == POOLED_SEED`` pool the runs of all seeds (AUC, TPR and CIs recomputed on
    the pooled taus).

    Parameters
    ----------
    n_runs : int, default 300
        Runs per group (ignored if ``sim`` is given).
    seeds : sequence of int, default (1, 2, 3)
        Master seeds.
    sigma_ends : sequence of float, default (0.10, 0.15)
        Final noise amplitudes of the noise-ramp and mixed groups.
    sim : SimConfig, optional
        Simulation settings; default is the baseline of ``configs/default.yaml``.
        ``sim.sigma`` is the initial (and control) noise amplitude.
    indicators : IndicatorConfig, optional
        Indicator settings; default is the baseline.
    n_boot : int, default 1000
        Bootstrap replicates per interval.

    Returns
    -------
    pandas.DataFrame
        One row per (scenario, seed or pooled, indicator) with the columns
        :data:`FRAME_COLUMNS`. ``change_pos`` / ``change_null`` are the median over valid runs
        of the last-to-first ratio (variance) or difference (AR(1)) of the rolling indicator
        in the positive and null group.
    """
    base_sim, base_ind = default_configs(n_runs)
    sim_cfg = base_sim if sim is None else sim
    ind_cfg = base_ind if indicators is None else indicators
    scenarios = build_scenarios(sigma_ends, sim_cfg.r_end)
    groups: dict[str, Group] = {}
    for sc in scenarios:
        groups[sc.pos.name] = sc.pos
        groups[sc.null.name] = sc.null

    per_seed: dict[int, dict[str, GroupStats]] = {}
    for seed in seeds:
        per_seed[seed] = {
            name: group_stats(simulate_group(sim_cfg, group, seed), ind_cfg)
            for name, group in groups.items()
        }

    rows: list[dict[str, Any]] = []
    for sc in scenarios:
        for seed in seeds:
            stats = per_seed[seed]
            rows += _rows(
                sc, seed, stats[sc.pos.name], stats[sc.null.name], sim_cfg, ind_cfg.fpr, n_boot
            )
        pos_pooled = _pool([per_seed[s][sc.pos.name] for s in seeds])
        null_pooled = _pool([per_seed[s][sc.null.name] for s in seeds])
        rows += _rows(sc, POOLED_SEED, pos_pooled, null_pooled, sim_cfg, ind_cfg.fpr, n_boot)
    return pd.DataFrame(rows, columns=list(FRAME_COLUMNS))


@dataclass(frozen=True, eq=False)
class IndicatorTraces:
    """Quantiles over runs of the rolling indicators of a noise-ramp group and the control.

    Attributes
    ----------
    t : numpy.ndarray
        Times of the analysed part of the run (from the first full window to the horizon),
        shape ``(n,)``.
    variance_noise, ar1_noise, variance_control, ar1_control : numpy.ndarray
        10th, 50th and 90th percentile over runs, shape ``(3, n)``, of the rolling variance and
        AR(1) of the noise-ramp group and of the control group.
    sigma_end : float
        Final noise amplitude of the noise-ramp group.
    """

    t: FloatArray
    variance_noise: FloatArray
    ar1_noise: FloatArray
    variance_control: FloatArray
    ar1_control: FloatArray
    sigma_end: float


def indicator_traces(sigma_end: float, n_runs: int = 300, seed: int = 1) -> IndicatorTraces:
    """Percentiles over runs of the rolling indicators, noise ramp versus control.

    The runs are those of :func:`run_confound` for the same ``seed`` (same group seeds). Samples
    after a run's analysis stop (a tip, or the horizon) are excluded from the percentiles.

    Parameters
    ----------
    sigma_end : float
        Final noise amplitude of the noise-ramp group.
    n_runs : int, default 300
        Runs per group.
    seed : int, default 1
        Master seed.

    Returns
    -------
    IndicatorTraces
        Percentile bands over the analysed time range.
    """
    sim, cfg = default_configs(n_runs)
    groups = (Group(f"noise_{sigma_end:.2f}", 0.0, sigma_end), Group("control", 0.0, None))
    bands: list[tuple[FloatArray, FloatArray]] = []
    t = np.empty(0)
    for group in groups:
        traj = simulate_group(sim, group, seed)
        horizon = analysis_horizon(traj.n_samples, cfg)
        tip = first_crossing(traj.x, cfg.tip_threshold)
        stop = analysis_stop(tip, traj.n_samples, cfg)
        ind = compute_indicators(traj.x, cfg.window, cfg.detrend_window)
        rows = np.arange(traj.n_samples)[:, None]
        keep = rows < stop[None, :]
        window = slice(cfg.window - 1, horizon)
        t = traj.t[window]
        out: list[FloatArray] = []
        for series in (ind.variance, ind.ar1):
            masked = np.where(keep, series, np.nan)[window]
            out.append(np.nanpercentile(masked, [10, 50, 90], axis=1))
        bands.append((out[0], out[1]))
    return IndicatorTraces(
        t=t,
        variance_noise=bands[0][0],
        ar1_noise=bands[0][1],
        variance_control=bands[1][0],
        ar1_control=bands[1][1],
        sigma_end=float(sigma_end),
    )


def _jsonable(value: Any) -> Any:
    """Convert numpy scalars and NaN to JSON-friendly values (NaN becomes ``None``)."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _indicator_entry(row: pd.Series) -> dict[str, Any]:
    return {
        "auc": float(row["auc"]),
        "auc_ci95": [float(row["auc_ci_lo"]), float(row["auc_ci_hi"])],
        "tpr_at_5pct_fpr": float(row["tpr"]),
        "tpr_ci95": [float(row["tpr_ci_lo"]), float(row["tpr_ci_hi"])],
        "median_tau_pos": float(row["median_tau_pos"]),
        "median_tau_null": float(row["median_tau_null"]),
        "median_change_pos": float(row["change_pos"]),
        "median_change_null": float(row["change_null"]),
    }


def summarise_confound(
    frame: pd.DataFrame, sim: SimConfig, indicators: IndicatorConfig, n_boot: int
) -> dict[str, Any]:
    """Build the compact JSON summary of a :func:`run_confound` table.

    Parameters
    ----------
    frame : pandas.DataFrame
        Output of :func:`run_confound`.
    sim : SimConfig
        Simulation settings used.
    indicators : IndicatorConfig
        Indicator settings used.
    n_boot : int
        Bootstrap replicates used for the intervals.

    Returns
    -------
    dict
        ``config``, a ``glossary`` and, per scenario, the pooled-over-seeds numbers
        (``pooled``) and the per-seed numbers (``per_seed``) for ``variance`` and ``ar1``.
        ``median_change_*`` is a ratio for the variance and a difference for the AR(1).
    """
    seeds = sorted(int(s) for s in frame["seed"].unique() if s != POOLED_SEED)
    horizon_fraction = indicators.analysis_fraction
    scenarios: dict[str, Any] = {}
    for name in dict.fromkeys(frame["scenario"]):
        sub = frame[frame["scenario"] == name]
        head = sub.iloc[0]
        s0 = float(head["sigma_start"])
        s1 = float(head["sigma_end"])
        s_analysis_end = s0 if not np.isfinite(s1) else s0 + (s1 - s0) * horizon_fraction
        entry: dict[str, Any] = {
            "pos_group": str(head["pos_group"]),
            "null_group": str(head["null_group"]),
            "sigma_start": s0,
            "sigma_end": s1,
            "sigma_at_analysis_end": s_analysis_end,
            "variance_ratio_expected_at_analysis_end": (s_analysis_end / s0) ** 2,
            "r_end": float(head["r_end"]),
        }
        pooled = sub[sub["seed"] == POOLED_SEED]
        entry["pooled"] = {
            ind: _indicator_entry(pooled[pooled["indicator"] == ind].iloc[0]) for ind in INDICATORS
        }
        first = pooled.iloc[0]
        entry["pooled"]["frac_pos_tipped_early"] = float(first["frac_pos_tipped_early"])
        entry["pooled"]["frac_null_tipped"] = float(first["frac_null_tipped"])
        entry["pooled"]["n_valid_pos"] = int(first["n_valid_pos"])
        entry["pooled"]["n_valid_null"] = int(first["n_valid_null"])
        entry["per_seed"] = {
            str(seed): {
                ind: _indicator_entry(
                    sub[(sub["seed"] == seed) & (sub["indicator"] == ind)].iloc[0]
                )
                for ind in INDICATORS
            }
            for seed in seeds
        }
        scenarios[str(name)] = entry
    return {
        "config": {
            "n_runs_per_group": int(frame["n_runs"].iloc[0]),
            "seeds": seeds,
            "duration": sim.duration,
            "dt": sim.dt,
            "sample_interval": sim.sample_interval,
            "sigma_start": sim.sigma,
            "r_start": sim.r_start,
            "window": indicators.window,
            "detrend_window": indicators.detrend_window,
            "analysis_fraction": indicators.analysis_fraction,
            "fpr": indicators.fpr,
            "n_boot": n_boot,
            "ci_method": "percentile bootstrap resampling runs, 95%",
        },
        "glossary": {
            "scenario": "positive group compared with null group (see pos_group, null_group)",
            "control": "r = 0 constant, sigma constant (0.05)",
            "fold": "r falls 0 -> -0.6, sigma constant: positive control (baseline experiment)",
            "noise_<s>": "r = 0 constant, sigma rises linearly 0.05 -> s over the run",
            "mixed_<s>": "r falls 0 -> -0.6 AND sigma rises 0.05 -> s",
            "mixed_vs_noise_<s>": "mixed_<s> against noise_<s> (is the fold visible under noise?)",
            "pooled": "all seeds pooled (runs concatenated; AUC, TPR and CIs recomputed)",
            "tpr_at_5pct_fpr": "fraction of positive runs above the 95th percentile of null taus; "
            "for a noise_<s> scenario this is the false-alarm rate of the indicator",
            "median_change": "median over valid runs of last/first rolling value (variance, "
            "a ratio) or last-first (AR(1), a difference), over the analysed part of the run",
            "sigma_at_analysis_end": "noise amplitude at the end of the analysed 60% of the run",
        },
        "scenarios": scenarios,
    }


def main(
    out_dir: Path | str | None = None,
    *,
    n_runs: int = 300,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    sigma_ends: Sequence[float] = DEFAULT_SIGMA_ENDS,
    n_boot: int = 1000,
) -> tuple[Path, Path]:
    """Run the experiment and write ``confound.parquet`` and ``confound.json``.

    Parameters
    ----------
    out_dir : pathlib.Path or str, optional
        Output directory; default is the project ``results`` directory.
    n_runs : int, default 300
        Runs per group.
    seeds : sequence of int, default (1, 2, 3)
        Master seeds.
    sigma_ends : sequence of float, default (0.10, 0.15)
        Final noise amplitudes.
    n_boot : int, default 1000
        Bootstrap replicates per interval.

    Returns
    -------
    tuple of pathlib.Path
        Paths of the Parquet table and of the JSON summary.
    """
    out = results_dir() if out_dir is None else Path(out_dir)
    sim, ind = default_configs(n_runs)
    frame = run_confound(seeds=seeds, sigma_ends=sigma_ends, sim=sim, indicators=ind, n_boot=n_boot)
    parquet_path = write_parquet(frame, out / "confound.parquet")
    summary = summarise_confound(frame, sim, ind, n_boot)
    json_path = out / "confound.json"
    json_path.write_text(json.dumps(_jsonable(summary), indent=2) + "\n", encoding="utf-8")
    return parquet_path, json_path


def _cli(argv: Sequence[str] | None = None) -> None:
    """Command-line entry point (``python -m tipping.confound``)."""
    parser = argparse.ArgumentParser(description="Noise-amplitude confound experiment.")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--n-runs", type=int, default=300)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--sigma-ends", type=float, nargs="+", default=list(DEFAULT_SIGMA_ENDS))
    parser.add_argument("--n-boot", type=int, default=1000)
    args = parser.parse_args(argv)
    parquet_path, json_path = main(
        args.out_dir,
        n_runs=args.n_runs,
        seeds=args.seeds,
        sigma_ends=args.sigma_ends,
        n_boot=args.n_boot,
    )
    print(f"wrote {parquet_path} and {json_path}")


if __name__ == "__main__":
    _cli()
