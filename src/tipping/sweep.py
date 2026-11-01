"""Noise-by-duration sweep of the early-warning experiment.

One *cell* is a triple ``(sigma, duration, seed)``: a full ramp-versus-control experiment
(:func:`tipping.evaluate.run_experiment`) with the window rule
``window = max(10, round(0.10 * duration / sample_interval))``,
``detrend_window = max(5, window // 4)`` (see :meth:`tipping.config.SweepConfig.indicator_config`).

Every cell gets its own master seed, a pure function of ``(sigma, duration, seed)``, so the
table does not depend on the number of workers, the order of execution or the rest of the grid.
:func:`run_sweep` writes ``sweep.parquet`` (one row per cell) and ``sweep_summary.parquet``
(per sigma and duration: mean over seeds with a percentile bootstrap 95% confidence interval).
"""

from __future__ import annotations

import itertools
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import typer
from joblib import Parallel, delayed

from tipping.config import SweepConfig, load_sweep_config
from tipping.evaluate import bootstrap_mean_ci, run_experiment
from tipping.io import write_parquet
from tipping.paths import config_dir, results_dir

SWEEP_COLUMNS: tuple[str, ...] = (
    "sigma",
    "duration",
    "seed",
    "n_runs",
    "window",
    "auc_var",
    "auc_ar1",
    "tpr_var",
    "tpr_ar1",
    "frac_ramp_tipped_early",
    "frac_null_tipped",
    "n_valid_ramp",
    "n_valid_null",
)
"""Columns of ``sweep.parquet`` in order."""

CI_METRICS: tuple[str, ...] = ("auc_var", "auc_ar1", "tpr_var", "tpr_ar1")
"""Metrics that get a mean and a bootstrap confidence interval in the summary."""

MEAN_ONLY_METRICS: tuple[str, ...] = (
    "frac_ramp_tipped_early",
    "frac_null_tipped",
    "n_valid_ramp",
    "n_valid_null",
)
"""Metrics that are only averaged over seeds in the summary."""

SUMMARY_COLUMNS: tuple[str, ...] = (
    "sigma",
    "duration",
    "n_seeds",
    "window",
    *(f"{m}_{s}" for m in CI_METRICS for s in ("mean", "ci_lo", "ci_hi")),
    *MEAN_ONLY_METRICS,
)
"""Columns of ``sweep_summary.parquet`` in order."""

SWEEP_FILE = "sweep.parquet"
SUMMARY_FILE = "sweep_summary.parquet"


@dataclass(frozen=True)
class Cell:
    """One experiment of the sweep.

    Attributes
    ----------
    sigma : float
        Noise amplitude.
    duration : float
        Ramp length in time units.
    seed : int
        Replication label from the configuration (not the RNG seed; see :func:`cell_seed`).
    """

    sigma: float
    duration: float
    seed: int


def default_sweep_config_path() -> Path:
    """Return the path of the default sweep configuration (``configs/sweep.yaml``)."""
    return config_dir() / "sweep.yaml"


def build_grid(cfg: SweepConfig) -> list[Cell]:
    """List all cells of a sweep, sorted by ``(sigma, duration, seed)``.

    Parameters
    ----------
    cfg : SweepConfig
        Sweep configuration.

    Returns
    -------
    list of Cell
        Cartesian product of the configured axes without duplicates.
    """
    triples = itertools.product(cfg.sigmas, cfg.durations, cfg.seeds)
    return [Cell(float(s), float(d), int(k)) for s, d, k in sorted(set(triples))]


def cell_seed(cell: Cell) -> int:
    """Derive the master RNG seed of a cell from ``(sigma, duration, seed)`` alone.

    Parameters
    ----------
    cell : Cell
        Grid cell.

    Returns
    -------
    int
        A 32-bit seed; different cells get statistically independent streams, and the value
        does not depend on any other cell, on execution order or on the number of workers.
    """
    entropy = [cell.seed, round(cell.sigma * 1_000_000), round(cell.duration * 1_000)]
    return int(np.random.SeedSequence(entropy).generate_state(1)[0])


def run_cell(cfg: SweepConfig, cell: Cell) -> dict[str, float | int]:
    """Run one cell and return its row of ``sweep.parquet``.

    Parameters
    ----------
    cfg : SweepConfig
        Sweep configuration (simulation settings and window rule).
    cell : Cell
        Grid cell to run.

    Returns
    -------
    dict
        One value per column of :data:`SWEEP_COLUMNS`.
    """
    sim = cfg.sim_config(cell.sigma, cell.duration, cell_seed(cell))
    indicators = cfg.indicator_config(cell.duration)
    result = run_experiment(sim, indicators, seed=sim.seed).result
    return {
        "sigma": cell.sigma,
        "duration": cell.duration,
        "seed": cell.seed,
        "n_runs": cfg.n_runs,
        "window": indicators.window,
        "auc_var": result.auc_var,
        "auc_ar1": result.auc_ar1,
        "tpr_var": result.tpr_var,
        "tpr_ar1": result.tpr_ar1,
        "frac_ramp_tipped_early": result.frac_ramp_tipped_early,
        "frac_null_tipped": result.frac_null_tipped,
        "n_valid_ramp": result.n_valid_ramp,
        "n_valid_null": result.n_valid_null,
    }


def _rows_to_frame(rows: list[dict[str, float | int]]) -> pd.DataFrame:
    """Assemble rows into a DataFrame with the schema columns, sorted by the cell keys."""
    frame = pd.DataFrame(rows, columns=list(SWEEP_COLUMNS))
    frame = frame.sort_values(["sigma", "duration", "seed"], kind="stable").reset_index(drop=True)
    return frame.astype(
        {
            "seed": "int64",
            "n_runs": "int64",
            "window": "int64",
            "n_valid_ramp": "int64",
            "n_valid_null": "int64",
        }
    )


def resolve_n_jobs(n_jobs: int | None, n_tasks: int) -> int:
    """Turn a requested worker count into a usable one.

    Parameters
    ----------
    n_jobs : int or None
        ``None`` or ``-1`` mean ``os.cpu_count()``; ``1`` means serial; other positive values
        are used as given.
    n_tasks : int
        Number of tasks; there is no point in more workers than tasks.

    Returns
    -------
    int
        Worker count, at least 1.
    """
    requested = (os.cpu_count() or 1) if n_jobs is None or n_jobs < 1 else n_jobs
    return max(1, min(requested, n_tasks))


def summarise(sweep: pd.DataFrame, n_boot: int = 1000) -> pd.DataFrame:
    """Aggregate the per-seed table to one row per ``(sigma, duration)``.

    For ``auc_var``, ``auc_ar1``, ``tpr_var`` and ``tpr_ar1`` the mean over seeds is reported
    together with a percentile bootstrap 95% confidence interval of that mean (resampling
    seeds; ``nan`` values are ignored, and a metric with no finite value gives ``nan``). The
    tipped fractions and the valid-run counts are averaged over seeds.

    Parameters
    ----------
    sweep : pandas.DataFrame
        Table with the columns of :data:`SWEEP_COLUMNS`.
    n_boot : int, default 1000
        Bootstrap resamples. The resampling seed is derived from the cell keys, so the output
        is deterministic.

    Returns
    -------
    pandas.DataFrame
        Columns :data:`SUMMARY_COLUMNS`, sorted by ``(sigma, duration)``.
    """
    rows: list[dict[str, float | int]] = []
    keys = sweep[["sigma", "duration"]].drop_duplicates().sort_values(["sigma", "duration"])
    for sigma_, duration_ in keys.itertuples(index=False):
        sigma, duration = float(sigma_), float(duration_)
        group = sweep[(sweep["sigma"] == sigma) & (sweep["duration"] == duration)]
        boot_seed = int(
            np.random.SeedSequence(
                [round(sigma * 1_000_000), round(duration * 1_000)]
            ).generate_state(1)[0]
        )
        row: dict[str, float | int] = {
            "sigma": sigma,
            "duration": duration,
            "n_seeds": int(group["seed"].nunique()),
            "window": int(group["window"].iloc[0]),
        }
        for metric in CI_METRICS:
            values = group[metric].to_numpy(dtype=np.float64)
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                mean = lo = hi = float("nan")
            else:
                mean = float(finite.mean())
                lo, hi = bootstrap_mean_ci(finite, n_boot=n_boot, seed=boot_seed)
            row[f"{metric}_mean"] = mean
            row[f"{metric}_ci_lo"] = lo
            row[f"{metric}_ci_hi"] = hi
        for metric in MEAN_ONLY_METRICS:
            row[metric] = float(group[metric].mean())
        rows.append(row)
    return pd.DataFrame(rows, columns=list(SUMMARY_COLUMNS))


def run_sweep(
    config_path: Path | None = None,
    out_dir: Path | None = None,
    n_jobs: int | None = None,
) -> Path:
    """Run the noise-by-duration sweep and write the result tables.

    Writes ``sweep.parquet`` (one row per ``(sigma, duration, seed)``) and
    ``sweep_summary.parquet`` into ``out_dir``. Re-running overwrites both files. The result is
    identical for any ``n_jobs`` because each cell has its own deterministic seed.

    Parameters
    ----------
    config_path : pathlib.Path, optional
        Sweep YAML file; defaults to ``configs/sweep.yaml``.
    out_dir : pathlib.Path, optional
        Output directory; defaults to :func:`tipping.paths.results_dir`.
    n_jobs : int, optional
        Worker processes; defaults to the ``n_jobs`` of the configuration (``-1``: all cores).
        If a process pool cannot be used the sweep falls back to serial execution.

    Returns
    -------
    pathlib.Path
        Path of ``sweep.parquet``.
    """
    cfg = load_sweep_config(config_path if config_path is not None else default_sweep_config_path())
    target_dir = Path(out_dir) if out_dir is not None else results_dir()
    cells = build_grid(cfg)
    # Long runs first so that the workers stay balanced; rows are sorted afterwards.
    schedule = sorted(cells, key=lambda c: (-c.duration, c.sigma, c.seed))
    workers = resolve_n_jobs(cfg.n_jobs if n_jobs is None else n_jobs, len(schedule))
    typer.echo(f"Sweep: {len(cells)} cells, {cfg.n_runs} runs per group, {workers} worker(s)")

    start = time.perf_counter()
    rows: list[dict[str, float | int]] = []

    def collect(stream: Iterable[dict[str, float | int]]) -> None:
        for row in stream:
            rows.append(row)
            typer.echo(
                f"[{len(rows):>3}/{len(schedule)}] sigma={row['sigma']:.2f} "
                f"duration={row['duration']:.0f} seed={row['seed']} "
                f"auc_var={row['auc_var']:.3f} auc_ar1={row['auc_ar1']:.3f} "
                f"({time.perf_counter() - start:.0f}s)"
            )

    if workers > 1:
        try:
            parallel = Parallel(n_jobs=workers, return_as="generator")
            collect(parallel(delayed(run_cell)(cfg, cell) for cell in schedule))
        except (OSError, ImportError, PermissionError) as error:
            typer.echo(f"Process pool unavailable ({error}); falling back to one worker.")
            rows.clear()
            workers = 1
    if workers == 1:
        collect(run_cell(cfg, cell) for cell in schedule)

    sweep = _rows_to_frame(rows)
    path = write_parquet(sweep, target_dir / SWEEP_FILE)
    write_parquet(summarise(sweep, n_boot=cfg.n_boot), target_dir / SUMMARY_FILE)
    typer.echo(f"Sweep finished in {time.perf_counter() - start:.0f}s -> {path}")
    return path
