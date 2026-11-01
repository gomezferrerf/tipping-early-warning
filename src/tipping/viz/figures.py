# ruff: noqa: RUF001  (the typographic minus sign is intended in figure text)
"""Static figures for the talk (Spanish) and the README (English).

Every slide figure is a function ``fig_*`` that writes one 200 dpi PNG and returns its path;
:func:`make_all` renders the whole set for one language. Slide figures carry no title (the slide
does) and keep text to a minimum; the README figures may carry a short title. All text comes
from :mod:`tipping.viz.labels`, all colours from :data:`tipping.viz.style.PALETTE`, and all
physics from the core modules (nothing is re-derived here).
"""

from __future__ import annotations

import functools
import logging
import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, ParamSpec, TypeVar

import matplotlib as mpl
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.figure import Figure
from matplotlib.gridspec import SubplotSpec
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter
from matplotlib.transforms import ScaledTranslation
from numpy.typing import NDArray

from tipping.config import ExperimentConfig, IndicatorConfig, load_config
from tipping.evaluate import EvalResult, Experiment, run_experiment
from tipping.indicators import compute_indicators
from tipping.io import read_parquet
from tipping.model import (
    FOLD_R,
    FOLD_X,
    classify_equilibria,
    growth_rate,
    lower_branch,
    middle_branch,
    potential,
    upper_branch,
)
from tipping.paths import assets_dir, default_config_path, results_dir
from tipping.simulate import Ramp, derive_seeds, first_crossing, simulate
from tipping.theory import ou_acf, ou_variance
from tipping.viz.labels import text
from tipping.viz.style import PALETTE, Lang, style_axes, style_params

FloatArray = NDArray[np.float64]
P = ParamSpec("P")
R = TypeVar("R")

SIZE_STD = (11.5, 5.75)
"""Slide canvas (inches, 2:1): the deck places figures about 11 in wide, so text keeps its size."""
SIZE_WIDE = (11.5, 5.0)
"""Slide canvas (inches, 2.3:1) for the three-panel and heatmap figures."""
FS_TICK = 15
FS_NOTE = 16
FS_TITLE = 17
FS_CAPTION = 20
FS_BIG = 22
DPI = 200
FOLD_JUMP_LOW = -2.0 / math.sqrt(3.0)
"""Equilibrium reached after the upward fold ``r = -r_c`` is crossed (``-2/sqrt(3)``)."""

EXAMPLE_SEED = 11
NOISE_SEED = 5
SIGNAL_SEED = 7
SIGNAL_R = (0.0, -0.33)
SIGNAL_SIGMA = 0.05
HEATMAP_TIPPED_LIMIT = 0.2
"""Cells whose control group tips more often than this are drawn as unreliable."""
HEATMAP_EARLY_LIMIT = 0.5
"""Cells where more ramp runs than this tip before 60% of the ramp are dotted."""
SWEEP_FILE = "sweep_summary.parquet"

_LOG = logging.getLogger(__name__)

_DASH = (0, (5, 3))
_DOT_STYLE: dict[str, Any] = {
    "marker": "o",
    "ms": 8,
    "mfc": PALETTE.ink,
    "mec": PALETTE.background,
    "mew": 1.4,
}
_LANDSCAPE_RS = (0.0, -0.2, -FOLD_R)
_README_LANDSCAPE_RS = (0.0, -0.2, -FOLD_R, -0.5)


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------


def _rc() -> dict[str, object]:
    """Return the rc parameters of the figures: project look plus projector-size fonts."""
    return {
        **style_params(),
        "mathtext.default": "regular",
        "hatch.linewidth": 1.2,
        "font.size": FS_TICK,
        "xtick.labelsize": FS_TICK,
        "ytick.labelsize": FS_TICK,
        "axes.labelsize": FS_NOTE,
        "axes.titlesize": FS_TITLE,
        "legend.fontsize": FS_TICK,
    }


def styled(func: Callable[P, R]) -> Callable[P, R]:
    """Run ``func`` inside ``matplotlib.rc_context`` with the figure style (no global state).

    Parameters
    ----------
    func : callable
        A function that builds and saves a figure.

    Returns
    -------
    callable
        The same function, with the style applied only while it runs.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with mpl.rc_context(_rc()):  # type: ignore[arg-type]
            return func(*args, **kwargs)

    return wrapper


def _new_figure(width: float, height: float) -> Figure:
    """Create an empty constrained-layout figure with the project background."""
    fig = Figure(figsize=(width, height), layout="constrained")
    engine = fig.get_layout_engine()
    if isinstance(engine, ConstrainedLayoutEngine):
        engine.set(wspace=0.07, hspace=0.07)
    return fig


def _axes(fig: Figure, lang: Lang, spec: SubplotSpec, *, grid: bool = False, **kwargs: Any) -> Axes:
    """Add a styled axes at ``spec`` whose numeric ticks use the language's decimal mark."""
    ax: Axes = fig.add_subplot(spec, **kwargs)
    style_axes(ax, grid=grid)
    formatter = FuncFormatter(lambda value, _: _tick(value, lang))
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)
    return ax


def _save(fig: Figure, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=DPI, facecolor=PALETTE.background)
    return path


def _default_dir(lang: Lang) -> Path:
    return results_dir() / "figures" / lang


def _loc(number: str, lang: Lang) -> str:
    """Localise a formatted number: decimal comma for Spanish, point for English."""
    return number.replace(".", ",") if lang == "es" else number


def _fixed(value: float, lang: Lang, digits: int = 2) -> str:
    """Format in fixed point with a typographic minus sign and the language's decimal mark."""
    return _loc(f"{value:.{digits}f}".replace("-", "−"), lang)


def _short(value: float, lang: Lang) -> str:
    """Format with three significant figures, a typographic minus and the decimal mark."""
    return _loc(f"{value:.3g}".replace("-", "−"), lang)


def auc_text(value: float, lang: Lang) -> str:
    """Format an AUC with two decimals, never rounding a value below 1 up to ``1,00``.

    A value such as 0.9996 would print as 1.00 and read as perfect separation, so the number of
    decimals grows (up to 6) until the text is no longer a rounded 1. The same rule as the deck's
    number formatter.

    Parameters
    ----------
    value : float
        AUC in [0, 1].
    lang : {"es", "en"}
        Language of the decimal mark.

    Returns
    -------
    str
        For example ``"0,87"``, ``"0,998"``, ``"0,9996"`` or ``"1,00"`` (only for exactly 1).
    """
    for digits in range(2, 7):
        out = f"{value:.{digits}f}"
        if value >= 1.0 or float(out) < 1.0:
            return _loc(out, lang)
    return _loc(f"{value:.6f}", lang)


def _tick(value: float, lang: Lang) -> str:
    """Tick label: shortest representation, typographic minus, language's decimal mark."""
    return _loc(f"{value:g}".replace("-", "−"), lang)


def _arrow(
    ax: Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    *,
    lw: float = 2.4,
    shrink: float = 0.0,
    style: str = "-|>",
    scale: float = 20.0,
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": style,
            "color": color,
            "lw": lw,
            "shrinkA": shrink,
            "shrinkB": shrink,
            "mutation_scale": scale,
        },
        zorder=5,
    )


def _no_frame(ax: Axes) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# --------------------------------------------------------------------------------------------
# Data builders (each is a pure function of its arguments and a seed)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Baseline:
    """The baseline ramp-versus-control experiment together with its configuration.

    Attributes
    ----------
    cfg : ExperimentConfig
        Configuration used (``configs/default.yaml`` with ``n_runs`` possibly reduced).
    experiment : Experiment
        Simulated trajectories and evaluation.
    """

    cfg: ExperimentConfig
    experiment: Experiment


def compute_baseline(n_runs: int = 300, seed: int | None = None) -> Baseline:
    """Run the baseline experiment of ``configs/default.yaml``.

    Parameters
    ----------
    n_runs : int, default 300
        Runs per group (the default matches the configuration).
    seed : int, optional
        Master seed; defaults to the configured seed.

    Returns
    -------
    Baseline
        Configuration and experiment.
    """
    cfg = load_config(default_config_path())
    cfg = cfg.model_copy(update={"sim": cfg.sim.model_copy(update={"n_runs": n_runs})})
    return Baseline(cfg=cfg, experiment=run_experiment(cfg.sim, cfg.indicators, seed))


@dataclass(frozen=True, eq=False)
class ExampleRuns:
    """One representative ramp run and one control run of the baseline setting.

    Attributes
    ----------
    t : numpy.ndarray
        Sample times.
    ramp, control : numpy.ndarray
        One series each, sampled at ``t``.
    tip_time : float
        Time at which the ramp run first falls below the tip threshold (``nan`` if it never does).
    fold_time : float
        Time at which the ramp reaches the fold (``nan`` if it does not).
    """

    t: FloatArray
    ramp: FloatArray
    control: FloatArray
    tip_time: float
    fold_time: float


def example_runs(n_runs: int = 30, seed: int = EXAMPLE_SEED) -> ExampleRuns:
    """Pick a typical ramp realisation (median tip time) and a control realisation.

    The ramp run is the one whose tip time is closest to the median tip time of ``n_runs``
    simulated runs, so the example is representative and not cherry-picked.

    Parameters
    ----------
    n_runs : int, default 30
        Number of candidate runs per group.
    seed : int, default ``EXAMPLE_SEED``
        Master seed.

    Returns
    -------
    ExampleRuns
        The selected series.
    """
    cfg = load_config(default_config_path()).sim
    ramp_seed, null_seed = derive_seeds(seed)
    common = {
        "sigma": cfg.sigma,
        "n_runs": n_runs,
        "dt": cfg.dt,
        "sample_every": cfg.sample_every,
        "x0": cfg.x0,
    }
    ramp = simulate(cfg.ramp(), seed=ramp_seed, **common)  # type: ignore[arg-type]
    null = simulate(cfg.control(), seed=null_seed, **common)  # type: ignore[arg-type]
    tips = first_crossing(ramp.x, 0.0)
    tipped = tips < ramp.n_samples
    pick = 0
    if tipped.any():
        median = float(np.median(tips[tipped]))
        pick = int(np.argmin(np.where(tipped, np.abs(tips - median), np.inf)))
    tip_time = float(ramp.t[tips[pick]]) if tipped[pick] else float("nan")
    fold = cfg.fold_time()
    return ExampleRuns(
        t=ramp.t,
        ramp=ramp.x[:, pick].copy(),
        control=null.x[:, 0].copy(),
        tip_time=tip_time,
        fold_time=float("nan") if fold is None else fold,
    )


@dataclass(frozen=True, eq=False)
class ValleyData:
    """Fluctuations of many runs around the upper equilibrium at a fixed ``r``.

    Attributes
    ----------
    r : float
        Control parameter.
    x_star : float
        Upper equilibrium.
    rate : float
        Growth rate ``lambda`` at ``x_star``.
    deviation : numpy.ndarray
        ``x - x_star`` after the burn-in, shape ``(n_samples, n_runs)``.
    kept : numpy.ndarray
        Boolean mask of the runs that never tipped (``x < 0.2``).
    dt : float
        Sampling interval.
    sigma : float
        Noise amplitude.
    """

    r: float
    x_star: float
    rate: float
    deviation: FloatArray
    kept: NDArray[np.bool_]
    dt: float
    sigma: float


def valley_data(
    r: float,
    *,
    sigma: float = SIGNAL_SIGMA,
    n_runs: int = 300,
    duration: float = 300.0,
    burn_in: float = 30.0,
    seed: int = SIGNAL_SEED,
) -> ValleyData:
    """Simulate fluctuations at constant ``r`` starting on the upper equilibrium.

    The same ``seed`` gives the same noise at different ``r``, so valleys can be compared with
    identical noise realisations.

    Parameters
    ----------
    r : float
        Control parameter (``r > -FOLD_R``).
    sigma : float, default 0.05
        Noise amplitude.
    n_runs : int, default 300
        Number of runs.
    duration : float, default 300
        Simulated time.
    burn_in : float, default 30
        Initial time discarded.
    seed : int
        Random seed.

    Returns
    -------
    ValleyData
        Deviations from the equilibrium and the mask of runs that did not tip.
    """
    x_star = float(upper_branch(float(r)))
    dt, every = 0.01, 50
    traj = simulate(Ramp.constant(r, duration), sigma, n_runs, dt, every, x_star, seed)
    start = round(burn_in / traj.sample_interval)
    kept = first_crossing(traj.x, 0.2) == traj.n_samples
    return ValleyData(
        r=float(r),
        x_star=x_star,
        rate=float(growth_rate(x_star)),
        deviation=traj.x[start:] - x_star,
        kept=kept,
        dt=traj.sample_interval,
        sigma=sigma,
    )


def _pooled_acf(dev: FloatArray, n_lags: int) -> FloatArray:
    """Autocorrelation of the pooled deviations at lags ``0 .. n_lags`` samples."""
    d = dev - dev.mean()
    n = d.shape[0]
    var = float(np.mean(d * d))
    return np.array([float(np.mean(d[: n - k] * d[k:])) / var for k in range(n_lags + 1)])


@dataclass(frozen=True, eq=False)
class Bands:
    """Median and 10-90% band over runs of the rolling indicators of one group.

    Attributes
    ----------
    t : numpy.ndarray
        Times kept (up to the plotting horizon).
    variance, ar1 : numpy.ndarray
        Shape ``(3, n_times)``: 10th percentile, median, 90th percentile (``nan`` where
        undefined). Samples at and after each run's tip (minus the detrending margin) are ignored.
    """

    t: FloatArray
    variance: FloatArray
    ar1: FloatArray


def indicator_bands(
    x: FloatArray, t: FloatArray, cfg: IndicatorConfig, t_max: float = 1200.0
) -> Bands:
    """Median and 10-90% band of the rolling indicators across runs.

    Parameters
    ----------
    x : numpy.ndarray
        States, shape ``(n_samples, n_runs)``.
    t : numpy.ndarray
        Sample times, shape ``(n_samples,)``.
    cfg : IndicatorConfig
        Windows and tip threshold.
    t_max : float, default 1200
        Last time kept.

    Returns
    -------
    Bands
        Percentile bands of the rolling variance and AR(1).
    """
    ind = compute_indicators(x, cfg.window, cfg.detrend_window)
    tip = first_crossing(x, cfg.tip_threshold)
    usable = np.arange(x.shape[0])[:, None] < (tip - cfg.detrend_window)[None, :]
    keep = t <= t_max

    def bands(values: FloatArray) -> FloatArray:
        masked = np.where(usable, values, np.nan)[keep]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-nan rows before the window
            result: FloatArray = np.nanpercentile(masked, [10, 50, 90], axis=1)
        return result

    return Bands(t=t[keep], variance=bands(ind.variance), ar1=bands(ind.ar1))


# --------------------------------------------------------------------------------------------
# Drawing blocks shared by several figures
# --------------------------------------------------------------------------------------------


def _landscape_ylim(rs: tuple[float, ...]) -> tuple[float, float]:
    deepest = min(
        float(np.min(potential(np.array(eq_x), r)))
        for r in rs
        for eq_x in [[e.x for e in classify_equilibria(r)]]
    )
    return deepest - 0.17, 0.55


def _draw_landscape(
    ax: Axes, r: float, lang: Lang, ball_x: float, ylim: tuple[float, float], *, labels: bool
) -> None:
    """Potential ``V(x; r)`` with its equilibria and the ball."""
    x = np.linspace(-1.5, 1.5, 700)
    ax.plot(x, potential(x, r), color=PALETTE.ink, lw=2.4, zorder=2, solid_capstyle="round")
    for eq in classify_equilibria(r):
        v = float(potential(eq.x, r))
        if eq.kind == "stable":
            style = {"marker": "o", "mfc": PALETTE.stable, "mec": PALETTE.background, "mew": 1.6}
        elif eq.kind == "unstable":
            style = {"marker": "o", "mfc": PALETTE.background, "mec": PALETTE.unstable, "mew": 2.4}
        else:
            style = {"marker": "D", "mfc": PALETTE.muted, "mec": PALETTE.background, "mew": 1.6}
        ax.plot([eq.x], [v], ls="none", ms=11, zorder=3, **style)  # type: ignore[arg-type]
    # The ball rests on top of its equilibrium marker (offset in points, not data units).
    lift = ScaledTranslation(0.0, 16.0 / 72.0, ax.figure.dpi_scale_trans)
    ax.plot(
        [ball_x],
        [float(potential(ball_x, r))],
        marker="o",
        ms=17,
        mfc=PALETTE.ink,
        mec=PALETTE.background,
        mew=1.6,
        ls="none",
        transform=ax.transData + lift,
        zorder=4,
    )
    ax.set_xlim(-1.68, 1.68)
    ax.set_ylim(*ylim)
    ax.set_title(text("r_caption", lang, r=_short(r, lang)), fontsize=FS_CAPTION, pad=6)
    _no_frame(ax)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(PALETTE.grid)
    if labels:
        ax.text(
            1.68, ylim[0] + 0.02, text("axis_x", lang), ha="right", va="bottom", fontsize=FS_NOTE
        )
        ax.text(
            -1.68,
            ylim[1] - 0.02,
            text("axis_potential", lang),
            ha="left",
            va="top",
            fontsize=FS_NOTE,
        )


def _ball_position(r: float) -> float:
    """Where the ball is: on the upper branch while it exists, else on the remaining minimum."""
    upper = float(upper_branch(float(r)))
    return upper if not math.isnan(upper) else float(classify_equilibria(r)[0].x)


def _landscape_panels(
    fig: Figure, specs: list[SubplotSpec], rs: tuple[float, ...], lang: Lang, *, axis_labels: bool
) -> list[Axes]:
    ylim = _landscape_ylim(rs)
    axes = []
    for i, (spec, r) in enumerate(zip(specs, rs, strict=True)):
        ax = _axes(fig, lang, spec)
        _draw_landscape(ax, r, lang, _ball_position(r), ylim, labels=axis_labels and i == 0)
        axes.append(ax)
    return axes


def _draw_bifurcation(ax: Axes, lang: Lang, *, hysteresis: bool) -> None:
    """Bifurcation diagram ``x*(r)``; with ``hysteresis`` the two jumps are drawn as a loop."""
    r_lim = 0.7
    r = np.unique(np.concatenate([np.linspace(-r_lim, r_lim, 1401), [-FOLD_R, FOLD_R]]))
    ax.axvspan(-FOLD_R, FOLD_R, facecolor=PALETTE.grid, alpha=0.75, lw=0, zorder=0)
    ax.plot(r, upper_branch(r), color=PALETTE.stable, lw=2.4, zorder=2)
    ax.plot(r, lower_branch(r), color=PALETTE.stable, lw=2.4, zorder=2)
    ax.plot(r, middle_branch(r), color=PALETTE.unstable, lw=2.4, ls=_DASH, zorder=2)
    for r_f, x_f in ((-FOLD_R, FOLD_X), (FOLD_R, -FOLD_X)):
        ax.plot(
            [r_f],
            [x_f],
            marker="D",
            ms=11,
            mfc=PALETTE.muted,
            mec=PALETTE.background,
            mew=1.6,
            ls="none",
            zorder=4,
        )
    ax.text(
        -FOLD_R - 0.025,
        FOLD_X,
        text("fold_left", lang),
        ha="right",
        va="center",
        fontsize=FS_NOTE,
        linespacing=1.15,
    )
    ax.text(
        FOLD_R + 0.025,
        -FOLD_X,
        text("fold_right", lang),
        ha="left",
        va="center",
        fontsize=FS_NOTE,
        linespacing=1.15,
    )
    ax.text(0.0, 1.74, text("bistable", lang), ha="center", va="top", fontsize=FS_NOTE)
    stable_label = text("stable", lang)
    ax.text(
        0.57,
        float(upper_branch(0.57)) + 0.1,
        stable_label,
        color=PALETTE.stable,
        ha="center",
        va="bottom",
        fontsize=FS_NOTE,
    )
    ax.text(
        -0.57,
        float(lower_branch(-0.57)) - 0.1,
        stable_label,
        color=PALETTE.stable,
        ha="center",
        va="top",
        fontsize=FS_NOTE,
    )
    ax.text(
        0.11,
        0.04,
        text("unstable", lang),
        color=PALETTE.unstable,
        ha="left",
        va="bottom",
        fontsize=FS_NOTE,
    )

    row = -1.72
    if hysteresis:
        up_end = float(upper_branch(FOLD_R))
        down_end = float(lower_branch(-FOLD_R))
        _arrow(ax, (-FOLD_R, FOLD_X), (-FOLD_R, down_end), PALETTE.ramp, lw=3.0, shrink=7.0)
        _arrow(ax, (FOLD_R, -FOLD_X), (FOLD_R, up_end), PALETTE.ramp, lw=3.0, shrink=7.0)
        top = float(upper_branch(0.15)) + 0.2
        bottom = float(lower_branch(-0.15)) - 0.2
        _arrow(ax, (0.3, top), (0.02, top), PALETTE.ramp, lw=2.0)
        ax.text(
            0.16,
            top + 0.07,
            text("r_decreasing", lang),
            color=PALETTE.ramp,
            ha="center",
            va="bottom",
            fontsize=FS_NOTE,
        )
        _arrow(ax, (-0.3, bottom), (-0.02, bottom), PALETTE.ramp, lw=2.0)
        ax.text(
            -0.16,
            bottom - 0.07,
            text("r_increasing", lang),
            color=PALETTE.ramp,
            ha="center",
            va="top",
            fontsize=FS_NOTE,
        )
        for r_f, y_from in ((-FOLD_R, down_end), (FOLD_R, -FOLD_X)):
            ax.plot(
                [r_f, r_f],
                [y_from - 0.05, row],
                color=PALETTE.muted,
                lw=1.2,
                ls=(0, (1.5, 2.5)),
                zorder=1,
            )
        _arrow(ax, (-FOLD_R, row), (FOLD_R, row), PALETTE.ink, lw=1.6, style="<|-|>", scale=16.0)
        width = _fixed(2.0 * FOLD_R, lang)
        ax.text(
            0.0,
            row - 0.07,
            text("loop_width", lang, width=width),
            ha="center",
            va="top",
            fontsize=FS_NOTE,
        )
        ax.set_ylim(-2.1, 1.8)
    else:
        _arrow(ax, (0.36, row), (-0.36, row), PALETTE.ramp, lw=2.6)
        ax.text(
            0.0,
            row + 0.08,
            text("r_decreasing", lang),
            color=PALETTE.ramp,
            ha="center",
            va="bottom",
            fontsize=FS_NOTE,
        )
        ax.set_ylim(-1.95, 1.8)
    ax.set_xlim(-r_lim, r_lim)
    ax.set_xticks([-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6])
    ax.set_yticks([-1.0, 0.0, 1.0])
    ax.set_xlabel(text("axis_r", lang))
    ax.set_ylabel(text("axis_xstar", lang), rotation=0, labelpad=14, va="center")


def _draw_series(ax: Axes, ex: ExampleRuns, lang: Lang, *, which: str, t_max: float) -> None:
    """One example series (``"ramp"``, ``"control"``) up to ``t_max``."""
    keep = ex.t <= t_max
    color = PALETTE.ramp if which == "ramp" else PALETTE.control
    series = ex.ramp if which == "ramp" else ex.control
    ax.plot(ex.t[keep], series[keep], color=color, lw=1.4)


def _draw_fold_line(ax: Axes, ex: ExampleRuns) -> None:
    ax.axvline(ex.fold_time, color=PALETTE.ink, lw=1.6, ls=_DASH, zorder=1)


def _draw_band_panel(
    ax: Axes,
    ramp: FloatArray,
    control: FloatArray,
    t: FloatArray,
    lang: Lang,
    *,
    scale: float,
    ylabel_key: str,
    legend: bool,
) -> None:
    """Median line and 10-90% band for the ramp and the control group of one indicator."""
    for q, color, fill in (
        (control, PALETTE.control, PALETTE.control_fill),
        (ramp, PALETTE.ramp, PALETTE.ramp_fill),
    ):
        ax.fill_between(t, q[0] * scale, q[2] * scale, color=fill, lw=0, zorder=1)
        ax.plot(t, q[1] * scale, color=color, lw=2.4, zorder=2)
    last = int(np.max(np.nonzero(np.isfinite(ramp[1]))[0]))
    x_label = float(t[last]) + 18.0
    ax.text(
        x_label,
        float(ramp[1, last]) * scale,
        text("ramp", lang),
        color=PALETTE.ramp,
        va="center",
        fontsize=FS_NOTE,
    )
    ax.text(
        x_label,
        float(control[1, last]) * scale,
        text("control", lang),
        color=PALETTE.control,
        va="center",
        fontsize=FS_NOTE,
    )
    finite = np.nonzero(np.isfinite(ramp[1]))[0]
    ax.set_xlim(float(t[finite[0]]), float(t[last]) + 240.0)
    ax.set_xlabel(text("time", lang))
    ax.set_ylabel(text(ylabel_key, lang))
    if legend:
        handles = [
            Line2D([], [], color=PALETTE.ramp, lw=2.4, label=text("ramp", lang)),
            Line2D([], [], color=PALETTE.control, lw=2.4, label=text("control", lang)),
            Patch(facecolor=PALETTE.grid, label=text("band_10_90", lang)),
        ]
        ax.legend(handles=handles, loc="upper left", fontsize=FS_NOTE)


def _draw_tau_hist(
    ax: Axes, res: EvalResult, lang: Lang, *, show_auc: bool, cfg_fpr: float
) -> None:
    """Histogram of the per-run Kendall tau of the AR(1), ramp versus control."""
    edges = np.linspace(-0.6, 1.0, 33)
    groups = (
        ("control", res.tau_null_ar1, PALETTE.control, PALETTE.control_fill),
        ("ramp", res.tau_ramp_ar1, PALETTE.ramp, PALETTE.ramp_fill),
    )
    counts_by_group = {key: np.histogram(taus, bins=edges)[0] for key, taus, _, _ in groups}
    top = float(max(np.max(c) for c in counts_by_group.values()))
    for key, _, color, fill in groups:
        counts = counts_by_group[key]
        ax.stairs(counts, edges, fill=True, color=fill, lw=0, zorder=1)
        ax.stairs(counts, edges, color=color, lw=1.8, zorder=2)
        mode = int(np.argmax(counts))
        ax.text(
            float(edges[mode]) + 0.025,
            float(counts[mode]) + 0.02 * top,
            text(key, lang),
            color=color,
            ha="center",
            va="bottom",
            fontsize=FS_NOTE,
        )
    threshold = float(np.quantile(res.tau_null_ar1, 1.0 - cfg_fpr))
    ax.axvline(threshold, color=PALETTE.ink, lw=1.6, ls=_DASH, zorder=3)
    ax.text(
        threshold - 0.02,
        top * 0.98,
        text("threshold", lang),
        ha="right",
        va="top",
        fontsize=FS_NOTE,
        linespacing=1.15,
    )
    if show_auc:
        ax.text(
            0.02,
            0.96,
            text("auc", lang, auc=auc_text(res.auc_ar1, lang)),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=FS_BIG,
        )
    ax.set_ylim(0.0, top * 1.22)
    ax.set_xlim(float(edges[0]), float(edges[-1]))
    ax.set_xlabel(text("kendall_ar1", lang))
    ax.set_ylabel(text("runs", lang))


# --------------------------------------------------------------------------------------------
# Slide figures
# --------------------------------------------------------------------------------------------


@styled
def fig_hook(lang: Lang, out_dir: Path | None = None, *, n_runs: int = 30) -> Path:
    """``s01_hook.png``: a calm noisy series that suddenly falls to a new level.

    Parameters
    ----------
    lang : {"es", "en"}
        Language (the figure has no text; kept for a uniform interface).
    out_dir : pathlib.Path, optional
        Output directory (default ``results/figures/<lang>``).
    n_runs : int, default 30
        Candidate runs from which the representative one is chosen.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    ex = example_runs(n_runs)
    fig = _new_figure(*SIZE_WIDE)
    ax = fig.add_subplot()
    keep = ex.t <= 1600.0
    ax.plot(ex.t[keep], ex.ramp[keep], color=PALETTE.ramp, lw=1.8)
    ax.set_ylim(float(np.min(ex.ramp[keep])) - 0.15, float(np.max(ex.ramp[keep])) + 0.15)
    ax.axis("off")
    return _save(fig, out_dir or _default_dir(lang), "s01_hook.png")


@styled
def fig_landscapes(
    lang: Lang, out_dir: Path | None = None, *, rs: tuple[float, ...] = _LANDSCAPE_RS
) -> Path:
    """``s04_landscapes.png``: the potential at three values of ``r`` with the ball in a valley.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.
    rs : tuple of float
        Control-parameter values of the panels.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    fig = _new_figure(*SIZE_WIDE)
    grid = fig.add_gridspec(1, len(rs))
    _landscape_panels(fig, [grid[0, i] for i in range(len(rs))], rs, lang, axis_labels=False)
    return _save(fig, out_dir or _default_dir(lang), "s04_landscapes.png")


@styled
def fig_bifurcation(lang: Lang, out_dir: Path | None = None) -> Path:
    """``s05_bifurcation.png``: static bifurcation diagram with the ramp direction.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    fig = _new_figure(*SIZE_STD)
    ax = _axes(fig, lang, fig.add_gridspec(1, 1)[0, 0])
    _draw_bifurcation(ax, lang, hysteresis=False)
    return _save(fig, out_dir or _default_dir(lang), "s05_bifurcation.png")


@styled
def fig_hysteresis(lang: Lang, out_dir: Path | None = None) -> Path:
    """``s07_hysteresis.png``: the bifurcation diagram with the two jumps forming a loop.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    fig = _new_figure(*SIZE_STD)
    ax = _axes(fig, lang, fig.add_gridspec(1, 1)[0, 0])
    _draw_bifurcation(ax, lang, hysteresis=True)
    return _save(fig, out_dir or _default_dir(lang), "s07_hysteresis.png")


@styled
def fig_noise(lang: Lang, out_dir: Path | None = None) -> Path:
    """``s08_noise.png``: deterministic relaxation next to the same system with noise.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    sigma = 0.05
    schedule = Ramp.constant(0.0, 12.0)
    clean = simulate(schedule, 0.0, 1, 0.01, 5, 1.3, NOISE_SEED)
    noisy = simulate(schedule, sigma, 1, 0.01, 5, 1.3, NOISE_SEED)
    fig = _new_figure(*SIZE_STD)
    grid = fig.add_gridspec(1, 2)
    axes = [_axes(fig, lang, grid[0, 0]), _axes(fig, lang, grid[0, 1])]
    captions = (text("no_noise", lang), text("with_noise", lang, sigma=_loc(f"{sigma:g}", lang)))
    for ax, traj, caption in zip(axes, (clean, noisy), captions, strict=True):
        ax.plot([0.0, float(traj.t[-1])], [1.0, 1.0], color=PALETTE.stable, lw=1.6, zorder=1)
        ax.plot(traj.t, traj.x[:, 0], color=PALETTE.ink, lw=1.8, zorder=2)
        ax.text(
            float(traj.t[-1]) + 0.3,
            1.0,
            text("equilibrium", lang),
            color=PALETTE.stable,
            ha="left",
            va="center",
            fontsize=FS_NOTE,
        )
        ax.set_title(caption, fontsize=FS_TITLE, loc="left")
        ax.set_ylim(0.88, 1.35)
        ax.set_xlim(0.0, float(traj.t[-1]) + 3.2)
        ax.set_xticks([0, 4, 8, 12])
        ax.set_yticks([1.0, 1.2])
        ax.set_xlabel(text("time", lang))
    axes[0].set_ylabel(text("axis_x", lang), rotation=0, labelpad=12, va="center")
    axes[1].tick_params(labelleft=False)
    return _save(fig, out_dir or _default_dir(lang), "s08_noise.png")


def _signal_figure(
    lang: Lang, *, n_runs: int, duration: float, title: bool, size: tuple[float, float]
) -> Figure:
    steep = valley_data(SIGNAL_R[0], n_runs=n_runs, duration=duration)
    flat = valley_data(SIGNAL_R[1], n_runs=n_runs, duration=duration)
    both = steep.kept & flat.kept
    if not both.any():
        both = np.ones_like(both)  # tiny test sizes: fall back to all runs
    example = int(np.argmax(both))
    valleys = (
        (steep, PALETTE.control, PALETTE.control_fill, "valley_steep", "lam_steep"),
        (flat, PALETTE.ramp, PALETTE.ramp_fill, "valley_flat", "lam_flat"),
    )

    fig = _new_figure(*size)
    grid = fig.add_gridspec(1, 3, width_ratios=[1.35, 1.0, 1.0])
    ax_t, ax_h, ax_c = (_axes(fig, lang, grid[0, i]) for i in range(3))

    # (a) the same noise realisation in the two valleys
    n_show = round(120.0 / steep.dt)
    time = np.arange(n_show) * steep.dt
    for data, color, _, _, _ in reversed(valleys):
        ax_t.plot(time, data.deviation[:n_show, example], color=color, lw=1.4)
    ax_t.set_ylim(-0.16, 0.16)
    ax_t.set_xlim(0.0, 120.0)
    ax_t.set_xlabel(text("time", lang))
    ax_t.set_title(text("deviation_title", lang), fontsize=FS_TITLE, loc="left")
    ax_t.set_yticks([-0.1, 0.0, 0.1])
    ax_t.set_xticks([0, 40, 80, 120])

    # (b) histograms against the Gaussian of the linearised (OU) theory
    edges = np.linspace(-0.2, 0.2, 61)
    grid_x = np.linspace(-0.2, 0.2, 400)
    for data, color, fill, _, _ in valleys:
        pooled = data.deviation[:, data.kept if data.kept.any() else slice(None)].ravel()
        counts, _ = np.histogram(pooled, bins=edges, density=True)
        ax_h.stairs(counts, edges, fill=True, color=fill, lw=0, zorder=1)
        ax_h.stairs(counts, edges, color=color, lw=1.6, zorder=2)
        var = float(ou_variance(data.sigma, data.rate))
        pdf = np.exp(-(grid_x**2) / (2.0 * var)) / math.sqrt(2.0 * math.pi * var)
        ax_h.plot(grid_x, pdf, color=PALETTE.ink, lw=1.6, ls=_DASH, zorder=3)
    ax_h.set_xlim(-0.2, 0.2)
    ax_h.set_ylim(bottom=0.0)
    ax_h.set_yticks([])
    ax_h.set_xticks([-0.1, 0.0, 0.1])
    ax_h.set_xlabel(text("deviation", lang))
    ax_h.set_title(text("distribution_title", lang), fontsize=FS_TITLE, loc="left")

    # (c) autocorrelation against exp(lambda * tau)
    n_lags = 12
    lags = np.arange(n_lags + 1) * steep.dt
    fine = np.linspace(0.0, float(lags[-1]), 200)
    for data, color, _, _, _ in valleys:
        pooled = data.deviation[:, data.kept if data.kept.any() else slice(None)]
        ax_c.plot(lags, _pooled_acf(pooled, n_lags), "o", ms=6, color=color, zorder=2)
        ax_c.plot(fine, ou_acf(data.rate, fine), color=PALETTE.ink, lw=1.6, ls=_DASH, zorder=3)
    lam_steep = _fixed(steep.rate, lang)
    lam_flat = _fixed(flat.rate, lang)
    # Colour-coded labels in the free upper-right area, in the same vertical order as the curves.
    ax_c.text(
        2.3,
        0.52,
        text("lam_flat", lang, lam=lam_flat),
        color=PALETTE.ramp,
        fontsize=FS_NOTE,
        va="center",
    )
    ax_c.text(
        2.3,
        0.38,
        text("lam_steep", lang, lam=lam_steep),
        color=PALETTE.control,
        fontsize=FS_NOTE,
        va="center",
    )
    ax_c.set_xlim(0.0, float(lags[-1]))
    ax_c.set_ylim(-0.08, 1.05)
    ax_c.set_xlabel(text("lag", lang))
    ax_c.set_title(text("autocorr_title", lang), fontsize=FS_TITLE, loc="left")

    handles = [
        Line2D(
            [],
            [],
            color=color,
            lw=2.4,
            label=text(key, lang, r=_short(data.r, lang), lam=_fixed(data.rate, lang)),
        )
        for data, color, _, key, _ in valleys
    ]
    handles.append(
        Line2D([], [], color=PALETTE.ink, lw=1.6, ls=_DASH, label=text("theory_ou", lang))
    )
    # With a title the legend goes below the panels so the two never compete for the top edge.
    legend_loc: Literal["outside lower center", "outside upper center"] = (
        "outside lower center" if title else "outside upper center"
    )
    fig.legend(handles=handles, loc=legend_loc, ncol=3, fontsize=FS_NOTE, frameon=False)
    if title:
        fig.suptitle(text("title_signal", lang), fontsize=FS_TITLE)
    return fig


@styled
def fig_signal(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    n_runs: int = 300,
    duration: float = 300.0,
    title: bool = False,
    filename: str = "s10_signal.png",
) -> Path:
    """``s10_signal.png``: critical slowing down, steep versus flat valley.

    Three panels: deviation series, histograms against the OU Gaussian, autocorrelation against
    ``exp(lambda tau)``. Runs that tip (``x < 0.2``) are discarded.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.
    n_runs : int, default 300
        Runs per valley.
    duration : float, default 300
        Simulated time per run (30 time units are discarded as burn-in).
    title : bool, default False
        Add a short title (README version).
    filename : str
        Output file name.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    size = (12.0, 5.4) if title else SIZE_WIDE
    fig = _signal_figure(lang, n_runs=n_runs, duration=duration, title=title, size=size)
    return _save(fig, out_dir or _default_dir(lang), filename)


@styled
def fig_experiment(lang: Lang, out_dir: Path | None = None, *, n_runs: int = 30) -> Path:
    """``s11_experiment.png``: one ramp series above one control series, same axes.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.
    n_runs : int, default 30
        Candidate runs for the representative realisation.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    ex = example_runs(n_runs)
    t_max = 1600.0
    fig = _new_figure(*SIZE_STD)
    grid = fig.add_gridspec(2, 1, hspace=0.08)
    top = _axes(fig, lang, grid[0, 0])
    bottom = _axes(fig, lang, grid[1, 0], sharex=top, sharey=top)
    _draw_series(top, ex, lang, which="ramp", t_max=t_max)
    _draw_series(bottom, ex, lang, which="control", t_max=t_max)
    for ax in (top, bottom):
        _draw_fold_line(ax, ex)
    top.tick_params(labelbottom=False)
    top.set_ylim(-1.5, 1.6)
    top.set_xlim(0.0, t_max)
    top.set_yticks([-1.0, 0.0, 1.0])
    top.text(
        0.008,
        0.95,
        text("ramp_series", lang),
        transform=top.transAxes,
        color=PALETTE.ramp,
        va="top",
        fontsize=FS_TITLE,
    )
    bottom.text(
        0.008,
        0.95,
        text("control_series", lang),
        transform=bottom.transAxes,
        color=PALETTE.control,
        va="top",
        fontsize=FS_TITLE,
    )
    top.text(
        ex.fold_time - 25.0,
        1.5,
        text("fold_time", lang, t=f"{ex.fold_time:.0f}"),
        va="top",
        ha="right",
        fontsize=FS_NOTE,
    )
    bottom.set_xlabel(text("time", lang))
    for ax in (top, bottom):
        ax.set_ylabel(text("axis_x", lang), rotation=0, labelpad=12, va="center")
    return _save(fig, out_dir or _default_dir(lang), "s11_experiment.png")


@styled
def fig_results(lang: Lang, base: Baseline, out_dir: Path | None = None) -> Path:
    """``s12_results.png``: rolling variance and AR(1), ramp versus control.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    base : Baseline
        Baseline experiment (see :func:`compute_baseline`).
    out_dir : pathlib.Path, optional
        Output directory.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    exp, cfg = base.experiment, base.cfg.indicators
    ramp = indicator_bands(exp.ramp.x, exp.ramp.t, cfg)
    null = indicator_bands(exp.null.x, exp.null.t, cfg)
    fig = _new_figure(*SIZE_STD)
    grid = fig.add_gridspec(1, 2)
    left, right = _axes(fig, lang, grid[0, 0]), _axes(fig, lang, grid[0, 1])
    _draw_band_panel(
        left,
        ramp.variance,
        null.variance,
        ramp.t,
        lang,
        scale=1e3,
        ylabel_key="rolling_variance",
        legend=True,
    )
    _draw_band_panel(
        right, ramp.ar1, null.ar1, ramp.t, lang, scale=1.0, ylabel_key="rolling_ar1", legend=False
    )
    left.set_ylim(bottom=0.0)
    return _save(fig, out_dir or _default_dir(lang), "s12_results.png")


@styled
def fig_control(lang: Lang, base: Baseline, out_dir: Path | None = None) -> Path:
    """``s13_control.png``: Kendall tau of the AR(1), ramp versus control, with the FPR threshold.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    base : Baseline
        Baseline experiment (see :func:`compute_baseline`).
    out_dir : pathlib.Path, optional
        Output directory.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    fig = _new_figure(*SIZE_STD)
    ax = _axes(fig, lang, fig.add_gridspec(1, 1)[0, 0])
    _draw_tau_hist(ax, base.experiment.result, lang, show_auc=True, cfg_fpr=base.cfg.indicators.fpr)
    return _save(fig, out_dir or _default_dir(lang), "s13_control.png")


# --------------------------------------------------------------------------------------------
# Sweep heatmaps
# --------------------------------------------------------------------------------------------


def load_summary(sweep_path: Path | None = None) -> pd.DataFrame:
    """Read the sweep summary table.

    Parameters
    ----------
    sweep_path : pathlib.Path, optional
        Parquet file (default ``results/sweep_summary.parquet``).

    Returns
    -------
    pandas.DataFrame
        One row per (sigma, duration).

    Raises
    ------
    FileNotFoundError
        If the file does not exist; the message says how to create it.
    """
    path = sweep_path if sweep_path is not None else results_dir() / SWEEP_FILE
    if not Path(path).is_file():
        msg = (
            f"sweep summary not found: {path}. Run `uv run tipping sweep` first "
            "(it writes results/sweep_summary.parquet)."
        )
        raise FileNotFoundError(msg)
    return read_parquet(path)


def _column(summary: pd.DataFrame, name: str) -> str:
    """Resolve ``name`` to a summary column (``<name>_mean`` if the table stores means)."""
    for candidate in (f"{name}_mean", name):
        if candidate in summary.columns:
            return candidate
    msg = f"sweep summary has no column {name!r} (columns: {', '.join(summary.columns)})"
    raise KeyError(msg)


def _pivot(summary: pd.DataFrame, name: str) -> pd.DataFrame:
    """Mean of ``name`` per (sigma, duration): rows sigma ascending, columns duration ascending."""
    column = _column(summary, name)
    table = summary.groupby(["sigma", "duration"])[column].mean().unstack("duration")
    return table.sort_index().sort_index(axis=1)


def _sequential_cmap(light: str, dark: str, name: str) -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(name, [light, dark])


def _luminance(rgb: tuple[float, float, float]) -> float:
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _draw_heat(
    ax: Axes,
    table: pd.DataFrame,
    cmap: LinearSegmentedColormap,
    norm: Normalize,
    lang: Lang,
    *,
    fmt: Callable[[float, Lang], str],
    hatched: pd.DataFrame | None,
    dotted: pd.DataFrame | None,
    ylabel: bool,
) -> None:
    """One annotated heatmap: sigma on y (low at the bottom), duration on x (short to long)."""
    values = table.to_numpy(dtype=float)
    n_rows, n_cols = values.shape
    ax.pcolormesh(
        np.arange(n_cols + 1),
        np.arange(n_rows + 1),
        np.ma.masked_invalid(values),
        cmap=cmap,
        norm=norm,
        edgecolors=PALETTE.background,
        linewidth=3.0,
    )
    flags = None if hatched is None else hatched.to_numpy(dtype=bool)
    dots = None if dotted is None else dotted.to_numpy(dtype=bool)
    for i in range(n_rows):
        for j in range(n_cols):
            value = values[i, j]
            if not np.isfinite(value):
                continue
            face = cmap(norm(value))
            dark_cell = _luminance((face[0], face[1], face[2])) < 0.3
            ink = PALETTE.background if dark_cell else PALETTE.ink
            is_hatched = flags is not None and bool(flags[i, j])
            effects = [pe.withStroke(linewidth=3.2, foreground=face)] if is_hatched else None
            if is_hatched:
                ax.add_patch(
                    Rectangle(
                        (j, i),
                        1.0,
                        1.0,
                        fill=False,
                        hatch="///",
                        edgecolor=(*to_rgb(PALETTE.ink), 0.45),
                        lw=0,
                        zorder=2,
                    )
                )
            if dots is not None and bool(dots[i, j]):
                ax.plot(
                    [j + 0.13],
                    [i + 0.86],
                    ls="none",
                    **_DOT_STYLE,
                    zorder=4,
                )
            ax.text(
                j + 0.5,
                i + 0.5,
                fmt(float(value), lang),
                ha="center",
                va="center",
                fontsize=FS_NOTE,
                color=ink,
                zorder=3,
                path_effects=effects,
            )
    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.set_xticks(np.arange(n_cols) + 0.5, [f"{int(d)}" for d in table.columns])
    ax.set_yticks(np.arange(n_rows) + 0.5, [_fixed(float(s), lang) for s in table.index])
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel(text("heat_x", lang))
    if ylabel:
        ax.set_ylabel(text("heat_y", lang))


def _heat_figure(
    lang: Lang,
    panels: list[tuple[pd.DataFrame, str, str]],
    cmap: LinearSegmentedColormap,
    norm: Normalize,
    *,
    fmt: Callable[[float, Lang], str],
    colorbar_key: str,
    colorbar_ticks: list[float],
    colorbar_labels: list[str],
    hatched: pd.DataFrame | None,
    dotted: pd.DataFrame | None,
    title: str | None,
    size: tuple[float, float],
) -> Figure:
    fig = _new_figure(*size)
    grid = fig.add_gridspec(1, len(panels))
    axes = []
    for i, (table, caption_key, _) in enumerate(panels):
        ax = _axes(fig, lang, grid[0, i])
        _draw_heat(
            ax, table, cmap, norm, lang, fmt=fmt, hatched=hatched, dotted=dotted, ylabel=i == 0
        )
        ax.set_title(text(caption_key, lang), fontsize=FS_TITLE, loc="left")
        axes.append(ax)
    bar = fig.colorbar(
        mpl.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axes, shrink=0.8, pad=0.02, aspect=22
    )
    bar.set_ticks(colorbar_ticks, labels=colorbar_labels)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0, labelsize=14)
    bar.set_label(text(colorbar_key, lang), fontsize=FS_NOTE)
    handles: list[Artist] = []
    if hatched is not None and bool(hatched.to_numpy(dtype=bool).any()):
        handles.append(
            Patch(
                facecolor=PALETTE.background,
                edgecolor=(*to_rgb(PALETTE.ink), 0.45),
                hatch="///",
                label=text("unreliable", lang),
            )
        )
    if dotted is not None and bool(dotted.to_numpy(dtype=bool).any()):
        handles.append(Line2D([], [], ls="none", **_DOT_STYLE, label=text("ramp_early", lang)))
    if handles:
        fig.legend(
            handles=handles,
            loc="outside lower center",
            ncol=len(handles),
            fontsize=FS_TICK,
            frameon=False,
        )
    if title:
        fig.suptitle(title, fontsize=FS_TITLE)
    return fig


@styled
def fig_heatmap(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    sweep_path: Path | None = None,
    summary: pd.DataFrame | None = None,
    title: bool = False,
    filename: str = "s14_heatmap.png",
) -> Path:
    """``s14_heatmap.png``: mean AUC of the AR(1) (left) and the variance (right) over the sweep.

    The colour scale is a single-hue violet ramp with fixed limits 0.5 to 1.0 so both panels are
    comparable. Two marks sit on top of it.

    Hatching (:data:`HEATMAP_TIPPED_LIMIT`)
        The control group tips on its own in strictly more than 20% of its runs, so the AUC is
        not a clean comparison. The test is strict (``>``). At sigma = 0.30 and duration 200 the
        fraction (mean over seeds) is 0.2000 up to floating point (0.19999999999999998), exactly
        on the limit, so that cell is *not* hatched; duration 400 (0.3544) is.
    Dot (:data:`HEATMAP_EARLY_LIMIT`)
        More than half of the ramp runs tip before 60% of the ramp.

    AUC values below 1 are never rounded up to 1.00 (see :func:`auc_text`).

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.
    sweep_path : pathlib.Path, optional
        Sweep summary Parquet (default ``results/sweep_summary.parquet``).
    summary : pandas.DataFrame, optional
        Summary table to use instead of reading ``sweep_path`` (used by the tests).
    title : bool, default False
        Add a short title (README version).
    filename : str
        Output file name.

    Returns
    -------
    pathlib.Path
        The written PNG.

    Raises
    ------
    FileNotFoundError
        If no table is given and the sweep summary does not exist.
    """
    table = load_summary(sweep_path) if summary is None else summary
    # Endpoints: AUC = 0.5 is chance (no information), so it gets the lightest violet (the
    # palette's fill tone); AUC = 1.0 is perfect separation, the full-strength ramp violet.
    cmap = _sequential_cmap(PALETTE.ramp_fill, PALETTE.ramp, "auc_violet")
    norm = Normalize(vmin=0.5, vmax=1.0, clip=True)
    unreliable = _pivot(table, "frac_null_tipped") > HEATMAP_TIPPED_LIMIT
    fig = _heat_figure(
        lang,
        [
            (_pivot(table, "auc_ar1"), "heat_ar1", ""),
            (_pivot(table, "auc_var"), "heat_variance", ""),
        ],
        cmap,
        norm,
        fmt=auc_text,
        colorbar_key="heat_colorbar",
        colorbar_ticks=[0.5, 0.75, 1.0],
        colorbar_labels=[_fixed(t, lang) for t in (0.5, 0.75, 1.0)],
        hatched=unreliable,
        dotted=_pivot(table, "frac_ramp_tipped_early") > HEATMAP_EARLY_LIMIT,
        title=text("title_heatmap", lang) if title else None,
        size=(12.0, 5.6) if title else SIZE_WIDE,
    )
    return _save(fig, out_dir or _default_dir(lang), filename)


@styled
def fig_tipped(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    sweep_path: Path | None = None,
    summary: pd.DataFrame | None = None,
) -> Path:
    """``b04_tipped.png`` (backup): fractions of control and ramp runs that tip on their own.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Output directory.
    sweep_path : pathlib.Path, optional
        Sweep summary Parquet.
    summary : pandas.DataFrame, optional
        Summary table to use instead of reading ``sweep_path``.

    Returns
    -------
    pathlib.Path
        The written PNG.

    Raises
    ------
    FileNotFoundError
        If no table is given and the sweep summary does not exist.
    """
    table = load_summary(sweep_path) if summary is None else summary
    cmap = _sequential_cmap(PALETTE.grid, PALETTE.ink, "tipped_slate")
    norm = Normalize(vmin=0.0, vmax=1.0, clip=True)
    fig = _heat_figure(
        lang,
        [
            (_pivot(table, "frac_null_tipped"), "tipped_null", ""),
            (_pivot(table, "frac_ramp_tipped_early"), "tipped_ramp", ""),
        ],
        cmap,
        norm,
        fmt=lambda value, lang: _loc(f"{value:.0%}", lang),
        colorbar_key="tipped_colorbar",
        colorbar_ticks=[0.0, 0.5, 1.0],
        colorbar_labels=[_tick(t, lang) for t in (0.0, 0.5, 1.0)],
        hatched=None,
        dotted=None,
        title=None,
        size=SIZE_WIDE,
    )
    return _save(fig, out_dir or _default_dir(lang), "b04_tipped.png")


# --------------------------------------------------------------------------------------------
# README figures
# --------------------------------------------------------------------------------------------


@styled
def readme_bifurcation(lang: Lang, out_dir: Path) -> Path:
    """``fig_bifurcation.png``: four landscapes above the bifurcation diagram.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path
        Output directory (``docs/assets`` for the README).

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    fig = _new_figure(12.0, 8.4)
    grid = fig.add_gridspec(2, 4, height_ratios=[1.0, 1.75])
    _landscape_panels(
        fig, [grid[0, i] for i in range(4)], _README_LANDSCAPE_RS, lang, axis_labels=True
    )
    ax = _axes(fig, lang, grid[1, :])
    _draw_bifurcation(ax, lang, hysteresis=False)
    fig.suptitle(text("title_bifurcation", lang), fontsize=FS_TITLE)
    return _save(fig, out_dir, "fig_bifurcation.png")


@styled
def readme_results(lang: Lang, base: Baseline, out_dir: Path, *, n_runs: int = 30) -> Path:
    """``fig_results.png``: 2x2 panel (series, variance, AR(1), tau histogram).

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    base : Baseline
        Baseline experiment.
    out_dir : pathlib.Path
        Output directory (``docs/assets`` for the README).
    n_runs : int, default 30
        Candidate runs for the representative series of the first panel.

    Returns
    -------
    pathlib.Path
        The written PNG.
    """
    exp, cfg = base.experiment, base.cfg.indicators
    ex = example_runs(n_runs)
    ramp = indicator_bands(exp.ramp.x, exp.ramp.t, cfg)
    null = indicator_bands(exp.null.x, exp.null.t, cfg)
    fig = _new_figure(12.0, 8.0)
    grid = fig.add_gridspec(2, 2)
    series, var_ax, ar1_ax, tau_ax = (_axes(fig, lang, grid[i // 2, i % 2]) for i in range(4))

    _draw_series(series, ex, lang, which="control", t_max=1600.0)
    _draw_series(series, ex, lang, which="ramp", t_max=1600.0)
    _draw_fold_line(series, ex)
    series.set_xlim(0.0, 1600.0)
    series.set_ylim(-1.5, 1.6)
    series.set_yticks([-1.0, 0.0, 1.0])
    series.set_xlabel(text("time", lang))
    series.set_ylabel(text("axis_x", lang), rotation=0, labelpad=12, va="center")
    series.text(
        ex.fold_time - 45.0,
        0.1,
        text("fold_time", lang, t=f"{ex.fold_time:.0f}"),
        va="center",
        ha="right",
        fontsize=FS_NOTE,
    )
    series.text(
        30.0, -1.0, text("ramp", lang), color=PALETTE.ramp, fontsize=FS_NOTE, va="center", ha="left"
    )
    series.text(
        30.0,
        1.22,
        text("control", lang),
        color=PALETTE.control,
        fontsize=FS_NOTE,
        va="center",
        ha="left",
    )

    _draw_band_panel(
        var_ax,
        ramp.variance,
        null.variance,
        ramp.t,
        lang,
        scale=1e3,
        ylabel_key="rolling_variance",
        legend=True,
    )
    var_ax.set_ylim(bottom=0.0)
    _draw_band_panel(
        ar1_ax, ramp.ar1, null.ar1, ramp.t, lang, scale=1.0, ylabel_key="rolling_ar1", legend=False
    )
    _draw_tau_hist(tau_ax, exp.result, lang, show_auc=True, cfg_fpr=cfg.fpr)
    fig.suptitle(text("title_results", lang), fontsize=FS_TITLE)
    return _save(fig, out_dir, "fig_results.png")


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------


def make_all(
    lang: Lang,
    out_dir: Path | None = None,
    sweep_path: Path | None = None,
    *,
    readme_dir: Path | None = None,
    confound_path: Path | None = None,
) -> list[Path]:
    """Render every static figure for ``lang``.

    Slide figures go to ``out_dir / lang`` (default ``results/figures/<lang>``), including the
    backup figure ``b05_noise_confound.png`` when the confound summary exists. The four README
    figures are English only and are written to ``docs/assets`` just when ``out_dir`` is ``None``
    (the default run, as the CLI does) or to ``readme_dir`` if that is given. Passing an
    ``out_dir`` therefore never touches the committed README assets.

    Parameters
    ----------
    lang : {"es", "en"}
        Label language.
    out_dir : pathlib.Path, optional
        Base output directory; the language is appended.
    sweep_path : pathlib.Path, optional
        Sweep summary Parquet (default ``results/sweep_summary.parquet``).
    readme_dir : pathlib.Path, optional
        Directory for the README figures (``lang == "en"`` only). If omitted they go to
        ``docs/assets`` when ``out_dir`` is ``None`` and are not written otherwise.
    confound_path : pathlib.Path, optional
        Confound summary (default ``results/confound.json``). If the file does not exist the
        figure ``b05`` is skipped with a logged warning.

    Returns
    -------
    list of pathlib.Path
        Every PNG written.

    Raises
    ------
    FileNotFoundError
        If the sweep summary is missing (checked before anything is rendered).
    """
    from tipping.viz import figures_extra  # imported here: figures_extra imports this module

    summary = load_summary(sweep_path)
    target = (out_dir if out_dir is not None else results_dir() / "figures") / lang
    base = compute_baseline()
    paths = [
        fig_hook(lang, target),
        fig_landscapes(lang, target),
        fig_bifurcation(lang, target),
        fig_hysteresis(lang, target),
        fig_noise(lang, target),
        fig_signal(lang, target),
        fig_experiment(lang, target),
        fig_results(lang, base, target),
        fig_control(lang, base, target),
        fig_heatmap(lang, target, summary=summary),
        fig_tipped(lang, target, summary=summary),
    ]
    confound = confound_path or results_dir() / figures_extra.SUMMARY_FILE
    if confound.is_file():
        paths.append(
            figures_extra.make_confound_figure(
                lang, target, summary=figures_extra.load_summary(confound)
            )
        )
    else:
        _LOG.warning("%s not found: skipping b05_noise_confound.png", confound)
    assets = readme_dir if readme_dir is not None else assets_dir() if out_dir is None else None
    if lang == "en" and assets is not None:
        paths += [
            readme_bifurcation(lang, assets),
            fig_signal(lang, assets, title=True, filename="fig_signal.png"),
            readme_results(lang, base, assets),
            fig_heatmap(lang, assets, summary=summary, title=True, filename="fig_heatmap.png"),
        ]
    return paths
