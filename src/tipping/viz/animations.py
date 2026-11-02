"""Three explanatory animations (MP4 + poster PNG) for the talk and the README.

* **A1 bifurcation**: the potential landscape ``V(x; r(t))`` next to the bifurcation diagram while
  ``r`` falls slowly from ``+0.3`` to ``-0.6``; the deterministic ball follows the valley, which
  flattens and disappears at the saddle-node bifurcation (fold), and falls into the other valley.
* **A2 noisy ball**: the same landscape with noise; ``r`` falls from ``0`` to ``-0.34`` (it stays
  *before* the fold) and the ball jitters more and more slowly. A live ``x(t)`` strip chart
  runs below. The single realization is illustrative: seed and noise level were chosen so that
  the run does not tip (``x`` stays above ``0.2``); this is enforced by a unit test.
* **A3 rolling window**: one ramp realization (sigma 0.05, duration 2000, ``r: 0 -> -0.6``) drawn
  progressively with the sliding window being analysed, the rolling variance and the rolling lag-1
  autocorrelation (ramp versus the median and 10-90% band of control runs) growing in step.
  Indicator curves stop where the analysis would stop (``detrend_window`` samples before the
  tip), because the centred detrending is contaminated by the jump after that.

All frames are 1920x1080, 30 fps, H.264 ``yuv420p`` with ``+faststart`` (PowerPoint compatible),
encoded with the ffmpeg binary shipped by ``imageio-ffmpeg``. Everything is precomputed once and
only line data / clip boxes change from frame to frame.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import matplotlib as mpl
import numpy as np
from matplotlib.animation import FFMpegWriter
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator
from matplotlib.transforms import Bbox, TransformedBbox
from numpy.typing import NDArray

from tipping.config import ExperimentConfig, load_config
from tipping.indicators import compute_indicators
from tipping.model import (
    FOLD_R,
    classify_equilibria,
    drift,
    growth_rate,
    lower_branch,
    middle_branch,
    potential,
    upper_branch,
)
from tipping.paths import default_config_path, results_dir
from tipping.simulate import Ramp, Trajectories, derive_seeds, first_crossing, simulate
from tipping.theory import ou_variance
from tipping.viz.style import PALETTE, Lang, style_axes, style_params

FloatArray = NDArray[np.float64]

# --------------------------------------------------------------------------------------
# Text (the only place where visible strings live)
# --------------------------------------------------------------------------------------
_TEXT: dict[str, dict[str, str]] = {
    "a1_title_left": {"es": "Paisaje de potencial", "en": "Potential landscape"},
    "a1_title_right": {"es": "Diagrama de bifurcación", "en": "Bifurcation diagram"},
    "a1_caption": {
        "es": "El valle derecho se aplana y desaparece",
        "en": "The right valley flattens and disappears",
    },
    "stable": {"es": "estable", "en": "stable"},
    "unstable": {"es": "inestable", "en": "unstable"},
    "state_axis": {"es": "estado x", "en": "state x"},
    "energy_axis": {"es": "potencial V", "en": "potential V"},
    "time_axis": {"es": "tiempo", "en": "time"},
    "a2_caption": {
        "es": "Fluctuaciones mayores y más lentas",
        "en": "Fluctuations grow and slow down",
    },
    "a3_variance": {"es": "Varianza", "en": "Variance"},
    "a3_ar1": {"es": "AR(1)", "en": "AR(1)"},
    "a3_window": {"es": "ventana", "en": "window"},
    "a3_ramp": {"es": "rampa", "en": "ramp"},
    "a3_control": {"es": "control", "en": "control"},
    "a3_caption": {
        "es": "Varianza y AR(1) suben antes del salto",
        "en": "Variance and AR(1) rise before the jump",
    },
    "a3_note": {
        "es": "an\u00e1lisis hasta poco antes del pliegue",
        "en": "analysis stops just before the fold",
    },
}


def _text(key: str, lang: Lang) -> str:
    """Return the string ``key`` in ``lang``."""
    return _TEXT[key][lang]


def _loc(number: str, lang: Lang) -> str:
    """Localise a formatted number: decimal comma for Spanish, point for English."""
    return number.replace(".", ",") if lang == "es" else number


def _tick_formatter(lang: Lang) -> FuncFormatter:
    """Tick formatter with a typographic minus and the language's decimal mark."""
    return FuncFormatter(lambda v, _pos: _loc(f"{v:g}".replace("-", "\N{MINUS SIGN}"), lang))


def _localise_ticks(lang: Lang, *axes: Axes) -> None:
    """Apply :func:`_tick_formatter` to both axes of every given ``Axes``."""
    fmt = _tick_formatter(lang)
    for ax in axes:
        ax.xaxis.set_major_formatter(fmt)
        ax.yaxis.set_major_formatter(fmt)


def _r_label(r: float, lang: Lang) -> str:
    """Format the running control-parameter readout (typographic minus, localised decimals)."""
    return _loc(f"r = {r:.2f}".replace("-", "\N{MINUS SIGN}"), lang)


# --------------------------------------------------------------------------------------
# Shared constants
# --------------------------------------------------------------------------------------
FIG_W_IN = 12.8
FIG_H_IN = 7.2
DEFAULT_WIDTH = 1920
FONT_BASE = 22
FONT_LABEL = 24
FONT_TITLE = 26
FONT_CAPTION = 26
FONT_NOTE = 18
LINE_W = 2.4

A1_R_START = 0.3
A1_R_END = -0.6
A1_RATE = 0.005  # |dr/dt| of the slow ramp (time units^-1)
A1_DURATION = 16.0
A1_HOLDS = (1.0, 1.6)  # seconds held before and after the motion

A2_DURATION = 14.5
A2_HOLDS = (0.5, 1.0)  # seconds held before and after the motion
A2_SIGMA = 0.16  # illustrative only: about 3x the baseline noise so the jitter is visible
A2_SEED = 4
A2_R_END = -0.34
A2_SAMPLE_DT = 0.2  # simulated time per video frame
A2_MIN_X = 0.2  # the realization must stay above this level (does not tip)

A3_N_RAMP = 60  # ramp runs to choose the realization from
A3_N_CONTROL = 200  # control runs behind the median and the 10-90% band
A3_DURATION = 19.5
A3_HOLDS = (0.8, 2.7)  # seconds held before and after the motion

_X_LIM = (-1.6, 1.6)


_P = ParamSpec("_P")
_R = TypeVar("_R")


def baseline_config() -> ExperimentConfig:
    """Load the baseline experiment configuration (``configs/default.yaml``).

    Returns
    -------
    tipping.config.ExperimentConfig
        Source of ``dt``, ``sample_every``, ``sigma``, ``x0``, the ramp and the indicator windows.
    """
    return load_config(default_config_path())


def _rc_params() -> dict[Any, Any]:
    """Return the project look plus the bundled ffmpeg path (applied only via ``rc_context``)."""
    import imageio_ffmpeg

    params: dict[Any, Any] = dict(style_params())
    params["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    return params


def _styled(func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Run ``func`` inside ``matplotlib.rc_context`` so the process-wide rcParams stay untouched."""

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with mpl.rc_context(_rc_params()):
            return func(*args, **kwargs)

    return wrapper


def _new_figure(width: int) -> tuple[Figure, float]:
    """Create a 16:9 figure that renders to ``width`` x ``width * 9 / 16`` pixels.

    Parameters
    ----------
    width : int
        Output width in pixels; must be a multiple of 128 so that both dimensions are even
        integers and the figure layout is resolution independent.

    Returns
    -------
    tuple of (matplotlib.figure.Figure, float)
        The figure (Agg canvas attached) and its dpi.
    """
    if width % 128 != 0 or width <= 0:
        msg = f"width must be a positive multiple of 128, got {width}"
        raise ValueError(msg)
    dpi = width / FIG_W_IN
    fig = Figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=dpi, facecolor=PALETTE.background)
    FigureCanvasAgg(fig)
    return fig, dpi


def _render(
    fig: Figure,
    update: Callable[[int], None],
    n_frames: int,
    fps: int,
    video_path: Path,
    poster_path: Path,
    poster_frame: int,
    dpi: float,
) -> None:
    """Encode ``n_frames`` frames to an H.264 MP4 and save a poster PNG.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figure whose artists ``update`` modifies.
    update : callable
        ``update(i)`` sets the state of every artist for frame ``i``.
    n_frames : int
        Number of frames.
    fps : int
        Frames per second.
    video_path, poster_path : pathlib.Path
        Output files; parent directories are created.
    poster_frame : int
        Index of the frame saved as the poster.
    dpi : float
        Figure dpi (the poster is exported at 4/3 of it: 2560x1440 for a 1920-pixel clip).
    """
    video_path.parent.mkdir(parents=True, exist_ok=True)
    writer = FFMpegWriter(
        fps=fps,
        codec="libx264",
        extra_args=[
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-movflags",
            "+faststart",
        ],
    )
    with writer.saving(fig, str(video_path), dpi):
        for i in range(n_frames):
            update(i)
            writer.grab_frame()
    update(poster_frame)
    fig.savefig(poster_path, dpi=dpi * 4.0 / 3.0, facecolor=PALETTE.background)


def _frame_counts(
    duration: float, fps: int, hold_start: float, hold_end: float
) -> tuple[int, int, int]:
    """Split a clip into (start-hold, motion, end-hold) frame counts.

    Holds are given in seconds and capped at a quarter of the clip so that very short test clips
    still contain motion.
    """
    n = max(round(duration * fps), 4)
    n_start = max(min(round(hold_start * fps), n // 4), 1)
    n_end = max(min(round(hold_end * fps), n // 4), 1)
    return n_start, n - n_start - n_end, n_end


def _ball_on_curve(
    x: float, r: float, *, sx: float, sy: float, radius_px: float
) -> tuple[float, float]:
    """Centre (in data units) of a ball of radius ``radius_px`` resting on ``V(., r)`` at ``x``.

    The ball touches the curve at abscissa ``x`` along the local normal, so on the bottom of a
    valley it sits exactly above the minimum. ``sx`` and ``sy`` are pixels per data unit.
    """
    slope = -drift(x, r)  # dV/dx
    nx, ny = -sy * slope, sx  # upward normal in pixels
    norm = math.hypot(nx, ny)
    v = potential(x, r)
    return x + radius_px * nx / norm / sx, v + radius_px * ny / norm / sy


def _plain_axes(ax: Axes) -> None:
    """Style ``ax`` without any grid lines."""
    style_axes(ax)
    ax.grid(False)


def _pixels_per_unit(ax: Axes) -> tuple[float, float]:
    """Pixels per data unit along x and y (axes position and limits must be final)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return float(ax.bbox.width / (x1 - x0)), float(ax.bbox.height / abs(y1 - y0))


def _valley_markers(ax: Axes) -> tuple[Line2D, Line2D]:
    """Create the (stable, unstable) equilibrium markers: filled blue dot, hollow coral ring.

    Both are drawn above the ball so that the dot under the ball stays visible.
    """
    (stable,) = ax.plot(
        [], [], ls="none", marker="o", ms=11, color=PALETTE.stable, mec=PALETTE.background,
        mew=1.5, zorder=6, clip_on=False,
    )  # fmt: skip
    (unstable,) = ax.plot(
        [], [], ls="none", marker="o", ms=13, mfc=PALETTE.background, mec=PALETTE.unstable,
        mew=3, zorder=6, clip_on=False,
    )  # fmt: skip
    return stable, unstable


def _update_valley_markers(stable: Line2D, unstable: Line2D, r: float) -> None:
    """Move the equilibrium markers to the roots of the landscape at control value ``r``."""
    eqs = classify_equilibria(r)
    xs_s = [e.x for e in eqs if e.kind == "stable"]
    xs_u = [e.x for e in eqs if e.kind != "stable"]
    stable.set_data(xs_s, [potential(x, r) for x in xs_s])
    unstable.set_data(xs_u, [potential(x, r) for x in xs_u])


def _style_landscape_axes(ax: Axes, y_lim: tuple[float, float], lang: Lang) -> None:
    """Apply the common look of the potential-landscape axes."""
    _plain_axes(ax)
    ax.set_xlim(*_X_LIM)
    ax.set_ylim(*y_lim)
    ax.set_xticks([-1, 0, 1])
    ax.set_yticks([])
    ax.tick_params(labelsize=FONT_BASE)
    ax.set_xlabel(_text("state_axis", lang), fontsize=FONT_LABEL)
    ax.set_ylabel(_text("energy_axis", lang), fontsize=FONT_LABEL)
    _localise_ticks(lang, ax)


# --------------------------------------------------------------------------------------
# A1: bifurcation
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FallTrajectory:
    """Deterministic trajectory of the ball while ``r`` falls linearly.

    Attributes
    ----------
    t : numpy.ndarray
        Times, shape ``(n,)``.
    r : numpy.ndarray
        Control parameter ``r(t)``.
    x : numpy.ndarray
        Ball position.
    """

    t: FloatArray
    r: FloatArray
    x: FloatArray


def deterministic_fall(
    rate: float = A1_RATE,
    r_start: float = A1_R_START,
    r_end: float = A1_R_END,
    dt: float | None = None,
) -> FallTrajectory:
    """Integrate ``dx/dt = r(t) + x - x**3`` with ``r(t) = r_start - rate * t`` (RK4).

    The ball starts on the upper branch at ``r_start`` and the integration stops when ``r``
    reaches ``r_end``.

    Parameters
    ----------
    rate : float
        Speed of the ramp, ``-dr/dt`` (small: the ball tracks the valley).
    r_start, r_end : float
        Initial and final control parameter (``r_end < r_start``).
    dt : float, optional
        Integration step (default: the baseline ``sim.dt``).

    Returns
    -------
    FallTrajectory
        Sampled ``(t, r, x)``.
    """
    dt = baseline_config().sim.dt if dt is None else dt
    n = round((r_start - r_end) / rate / dt)
    t = np.arange(n + 1, dtype=np.float64) * dt
    r = r_start - rate * t
    x = np.empty(n + 1)
    x[0] = float(upper_branch(r_start))
    for i in range(n):
        r0, r1 = float(r[i]), r_start - rate * (t[i] + dt)
        rm = 0.5 * (r0 + r1)
        xi = float(x[i])
        k1 = drift(xi, r0)
        k2 = drift(xi + 0.5 * dt * k1, rm)
        k3 = drift(xi + 0.5 * dt * k2, rm)
        k4 = drift(xi + dt * k3, r1)
        x[i + 1] = xi + dt / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return FallTrajectory(t=t, r=r, x=x)


def _a1_frames(
    traj: FallTrajectory, n_motion: int, slow_fall: float = 25.0
) -> tuple[FloatArray, FloatArray]:
    """Sample the trajectory at ``n_motion`` video frames, slowing down while the ball moves fast.

    Video time is proportional to ``integral (1 + slow_fall * |dx/dt|) dt``, so the long quiet
    stretch is quick and the fall at the fold takes a visible share of the clip.
    """
    speed = np.abs(np.gradient(traj.x, traj.t))
    weight = 1.0 + slow_fall * speed
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (weight[1:] + weight[:-1]) * np.diff(traj.t))])
    targets = np.linspace(0.0, cum[-1], n_motion)
    t_f = np.interp(targets, cum, traj.t)
    return np.interp(t_f, traj.t, traj.r), np.interp(t_f, traj.t, traj.x)


@_styled
def animate_bifurcation(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    fps: int = 30,
    duration: float = A1_DURATION,
    width: int = DEFAULT_WIDTH,
) -> tuple[Path, Path]:
    """Render animation A1: landscape and bifurcation diagram with a falling ball.

    Parameters
    ----------
    lang : {"es", "en"}
        Language of the on-screen text.
    out_dir : pathlib.Path, optional
        Directory for ``a1_bifurcation.mp4`` and ``a1_bifurcation_poster.png``
        (default ``results/animations/<lang>``).
    fps : int, default 30
        Frames per second.
    duration : float, default 16.0
        Clip length in seconds (a short hold at both ends is included).
    width : int, default 1920
        Output width in pixels (multiple of 128; the height is ``width * 9 / 16``).

    Returns
    -------
    tuple of (pathlib.Path, pathlib.Path)
        The MP4 and the poster PNG.
    """
    out = out_dir if out_dir is not None else results_dir() / "animations" / lang
    video, poster = out / "a1_bifurcation.mp4", out / "a1_bifurcation_poster.png"
    fig, dpi = _new_figure(width)
    n_start, n_motion, n_end = _frame_counts(duration, fps, *A1_HOLDS)
    traj = deterministic_fall()
    r_m, x_m = _a1_frames(traj, n_motion)
    r_f = np.concatenate([np.full(n_start, r_m[0]), r_m, np.full(n_end, r_m[-1])])
    x_f = np.concatenate([np.full(n_start, x_m[0]), x_m, np.full(n_end, x_m[-1])])
    n_frames = len(r_f)

    # Left: landscape.
    ax_l = fig.add_axes((0.095, 0.235, 0.385, 0.565))
    _style_landscape_axes(ax_l, (-1.15, 1.45), lang)
    ax_l.set_title(_text("a1_title_left", lang), fontsize=FONT_TITLE, pad=14)
    xs = np.linspace(*_X_LIM, 400)
    (land,) = ax_l.plot(xs, potential(xs, float(r_f[0])), color=PALETTE.ink, lw=3.2, zorder=2)
    mk_stable, mk_unstable = _valley_markers(ax_l)
    (ball,) = ax_l.plot(
        [], [], ls="none", marker="o", ms=24, color=PALETTE.ink, mec=PALETTE.background, mew=2,
        zorder=5, clip_on=False,
    )  # fmt: skip
    sx, sy = _pixels_per_unit(ax_l)
    radius_px = 12.0 * dpi / 72.0

    # Right: bifurcation diagram (fixed curves) with the moving marker.
    ax_r = fig.add_axes((0.595, 0.235, 0.385, 0.565))
    _plain_axes(ax_r)
    rs = np.linspace(-0.7, 0.45, 900)
    ax_r.plot(rs, upper_branch(rs), color=PALETTE.stable, lw=LINE_W + 0.4, zorder=2)
    ax_r.plot(rs, lower_branch(rs), color=PALETTE.stable, lw=LINE_W + 0.4, zorder=2)
    ax_r.plot(
        rs, middle_branch(rs), color=PALETTE.unstable, lw=LINE_W + 0.4, ls=(0, (4, 3)), zorder=2
    )
    ax_r.axvline(-FOLD_R, color=PALETTE.muted, lw=1.2, ls=":", zorder=1)
    ax_r.set_xlim(-0.7, 0.45)
    ax_r.set_ylim(-1.6, 1.6)
    ax_r.set_xticks([-0.6, -0.3, 0.0, 0.3])
    ax_r.set_yticks([-1, 0, 1])
    ax_r.tick_params(labelsize=FONT_BASE)
    ax_r.set_xlabel("r", fontsize=FONT_LABEL)
    ax_r.set_ylabel("x", fontsize=FONT_LABEL, rotation=0, labelpad=16)
    _localise_ticks(lang, ax_r)
    ax_r.set_title(_text("a1_title_right", lang), fontsize=FONT_TITLE, pad=14)
    ax_r.text(
        0.45, 1.3, _text("stable", lang), color=PALETTE.stable, fontsize=FONT_BASE, ha="right"
    )
    ax_r.text(
        0.45, -1.4, _text("stable", lang), color=PALETTE.stable, fontsize=FONT_BASE, ha="right"
    )
    ax_r.text(
        0.45, 0.25, _text("unstable", lang), color=PALETTE.unstable_text, fontsize=FONT_BASE,
        ha="right",
    )  # fmt: skip
    vline = ax_r.axvline(float(r_f[0]), color=PALETTE.ink, lw=1.4, zorder=3)
    (trail,) = ax_r.plot([], [], color=PALETTE.ink, lw=1.8, alpha=0.55, zorder=3)
    (marker,) = ax_r.plot(
        [], [], ls="none", marker="o", ms=15, color=PALETTE.ink, mec=PALETTE.background, mew=2,
        zorder=5, clip_on=False,
    )  # fmt: skip
    readout = fig.text(0.5, 0.945, "", fontsize=FONT_TITLE + 2, ha="center", va="center")
    fig.text(
        0.5, 0.012, _text("a1_caption", lang), ha="center", fontsize=FONT_CAPTION, color=PALETTE.ink
    )

    def update(i: int) -> None:
        r, x = float(r_f[i]), float(x_f[i])
        land.set_ydata(potential(xs, r))
        _update_valley_markers(mk_stable, mk_unstable, r)
        bx, by = _ball_on_curve(x, r, sx=sx, sy=sy, radius_px=radius_px)
        ball.set_data([bx], [by])
        vline.set_xdata([r, r])
        trail.set_data(r_f[: i + 1], x_f[: i + 1])
        marker.set_data([r], [x])
        readout.set_text(_r_label(r, lang))

    poster_frame = int(np.argmin(np.abs(r_f[: n_start + n_motion] + 0.37)))
    _render(fig, update, n_frames, fps, video, poster, poster_frame, dpi)
    return video, poster


# --------------------------------------------------------------------------------------
# A2: noisy ball
# --------------------------------------------------------------------------------------
def noisy_ball_realization(
    duration: float = A2_DURATION,
    fps: int = 30,
    *,
    sigma: float = A2_SIGMA,
    seed: int = A2_SEED,
) -> Trajectories:
    """Single noisy realization shown in animation A2 (one sample per video frame).

    ``r`` falls linearly from ``0`` to :data:`A2_R_END` (before the fold at ``-0.385``). The
    default ``sigma`` and ``seed`` give a run that does not tip (``x`` stays above
    :data:`A2_MIN_X`), so the clip illustrates growing, slowing jitter and not an escape.

    Parameters
    ----------
    duration : float
        Clip length in seconds (an end hold is included, see :func:`animate_noisy_ball`).
    fps : int
        Frames per second.
    sigma : float
        Noise amplitude.
    seed : int
        Seed of the random generator.

    Returns
    -------
    tipping.simulate.Trajectories
        One run, sampled every :data:`A2_SAMPLE_DT` time units.
    """
    _, n_motion, _ = _frame_counts(duration, fps, *A2_HOLDS)
    ramp = Ramp(0.0, A2_R_END, (n_motion - 1) * A2_SAMPLE_DT)
    sim = baseline_config().sim
    return simulate(
        ramp,
        sigma,
        1,
        dt=sim.dt,
        sample_every=round(A2_SAMPLE_DT / sim.dt),
        x0=sim.x0,
        seed=seed,
    )


@_styled
def animate_noisy_ball(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    fps: int = 30,
    duration: float = A2_DURATION,
    width: int = DEFAULT_WIDTH,
) -> tuple[Path, Path]:
    """Render animation A2: a noisy ball in the flattening valley plus a live ``x(t)`` strip.

    Parameters
    ----------
    lang : {"es", "en"}
        Language of the on-screen text.
    out_dir : pathlib.Path, optional
        Directory for ``a2_noisy_ball.mp4`` and ``a2_noisy_ball_poster.png``
        (default ``results/animations/<lang>``).
    fps : int, default 30
        Frames per second.
    duration : float, default 14.5
        Clip length in seconds (holds included).
    width : int, default 1920
        Output width in pixels (multiple of 128).

    Returns
    -------
    tuple of (pathlib.Path, pathlib.Path)
        The MP4 and the poster PNG.
    """
    out = out_dir if out_dir is not None else results_dir() / "animations" / lang
    video, poster = out / "a2_noisy_ball.mp4", out / "a2_noisy_ball_poster.png"
    fig, dpi = _new_figure(width)
    n_start, n_motion, n_end = _frame_counts(duration, fps, *A2_HOLDS)
    tr = noisy_ball_realization(duration, fps)
    t, r_s, x_s = tr.t, tr.r, tr.x[:, 0]
    n_frames = n_start + n_motion + n_end
    x_star = upper_branch(r_s)
    x_hill = middle_branch(r_s)
    # Linearised (Ornstein-Uhlenbeck) standard deviation around the valley bottom.
    std_eff = np.sqrt(ou_variance(tr.sigma, growth_rate(x_star)))
    caption_from = n_start + round(0.6 * n_motion)

    ax_l = fig.add_axes((0.085, 0.585, 0.895, 0.365))
    _style_landscape_axes(ax_l, (-0.8, 1.0), lang)
    xs = np.linspace(*_X_LIM, 500)
    (land,) = ax_l.plot(xs, potential(xs, 0.0), color=PALETTE.ink, lw=3.2, zorder=2)
    mk_stable, mk_unstable = _valley_markers(ax_l)
    (ball,) = ax_l.plot(
        [], [], ls="none", marker="o", ms=24, color=PALETTE.ink, mec=PALETTE.background, mew=2,
        zorder=5, clip_on=False,
    )  # fmt: skip
    sx, sy = _pixels_per_unit(ax_l)
    radius_px = 12.0 * dpi / 72.0
    readout = ax_l.text(
        0.02, 0.93, "", transform=ax_l.transAxes, fontsize=FONT_TITLE, ha="left", va="top"
    )

    ax_s = fig.add_axes((0.085, 0.205, 0.895, 0.24))
    style_axes(ax_s, grid=True)
    ax_s.set_xlim(0.0, float(t[-1]))
    ax_s.set_ylim(0.0, 1.35)
    ax_s.set_yticks([0.0, 0.5, 1.0])
    ax_s.tick_params(labelsize=FONT_BASE)
    ax_s.set_xlabel(_text("time_axis", lang), fontsize=FONT_LABEL)
    ax_s.set_ylabel("x", fontsize=FONT_LABEL, rotation=0, labelpad=16)
    _localise_ticks(lang, ax_s)
    ax_s.fill_between(
        t, x_star - std_eff, x_star + std_eff, color=PALETTE.stable_fill, lw=0, zorder=1
    )
    ax_s.plot(t, x_star, color=PALETTE.stable, lw=LINE_W, zorder=2)
    ax_s.plot(t, x_hill, color=PALETTE.unstable, lw=LINE_W, ls=(0, (4, 3)), zorder=2)
    (trace,) = ax_s.plot([], [], color=PALETTE.ink, lw=1.8, zorder=3)
    (head,) = ax_s.plot(
        [], [], ls="none", marker="o", ms=10, color=PALETTE.ink, mec=PALETTE.background, mew=1.5,
        zorder=4, clip_on=False,
    )  # fmt: skip
    caption = fig.text(
        0.5, 0.012, _text("a2_caption", lang), ha="center", fontsize=FONT_CAPTION, color=PALETTE.ink
    )
    caption.set_visible(False)

    def update(i: int) -> None:
        k = min(max(i - n_start, 0), len(t) - 1)
        r, x = float(r_s[k]), float(x_s[k])
        land.set_ydata(potential(xs, r))
        _update_valley_markers(mk_stable, mk_unstable, r)
        bx, by = _ball_on_curve(x, r, sx=sx, sy=sy, radius_px=radius_px)
        ball.set_data([bx], [by])
        trace.set_data(t[: k + 1], x_s[: k + 1])
        head.set_data([t[k]], [x])
        readout.set_text(_r_label(r, lang))
        caption.set_visible(i >= caption_from)

    late = slice(n_start + int(0.80 * n_motion), n_start + n_motion)
    k_late = np.arange(late.start, late.stop) - n_start
    poster_frame = late.start + int(np.argmax(np.abs(x_s[k_late] - x_star[k_late])))
    _render(fig, update, n_frames, fps, video, poster, poster_frame, dpi)
    return video, poster


# --------------------------------------------------------------------------------------
# A3: rolling window
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RollingData:
    """Precomputed series behind animation A3.

    Attributes
    ----------
    t : numpy.ndarray
        Sample times.
    x : numpy.ndarray
        The chosen ramp realization.
    tip_index : int
        First sample with ``x < 0``.
    end_index : int
        Last sample at which the indicator curves are drawn (``tip_index - detrend_window``).
    var_ramp, ar1_ramp : numpy.ndarray
        Rolling indicators of the realization (``nan`` outside ``[window - 1, end_index]``).
    var_ctrl, ar1_ctrl : numpy.ndarray
        Control medians and 10-90% bands, shape ``(3, n_samples)`` (10%, median, 90%).
    window_samples : int
        Rolling-window length in samples.
    sample_interval : float
        Time between samples.
    """

    t: FloatArray
    x: FloatArray
    tip_index: int
    end_index: int
    var_ramp: FloatArray
    ar1_ramp: FloatArray
    var_ctrl: FloatArray
    ar1_ctrl: FloatArray
    window_samples: int
    sample_interval: float


def rolling_window_data(
    *,
    seed: int | None = None,
    n_ramp: int = A3_N_RAMP,
    n_control: int = A3_N_CONTROL,
    duration: float | None = None,
    window: int | None = None,
    detrend_window: int | None = None,
) -> RollingData:
    """Simulate the ramp and control batches and pick the realization for animation A3.

    The chosen ramp run is the one that tips earliest among those tipping at or after the fold
    time (so it tips near the fold, not early). Every ``None`` argument defaults to the baseline
    configuration (:func:`baseline_config`). Indicators come from
    :func:`tipping.indicators.compute_indicators`.

    Parameters
    ----------
    seed : int, optional
        Master seed (ramp and control get independent derived seeds).
    n_ramp, n_control : int
        Number of ramp runs to choose from and of control runs for the median/band.
    duration : float, optional
        Ramp length.
    window, detrend_window : int, optional
        Rolling-window and detrending lengths in samples.

    Returns
    -------
    RollingData
        All arrays needed to draw the animation.

    Raises
    ------
    RuntimeError
        If no ramp run tips at or after the fold time.
    """
    cfg = baseline_config()
    sim = cfg.sim
    seed = sim.seed if seed is None else seed
    duration = sim.duration if duration is None else duration
    window = cfg.indicators.window if window is None else window
    detrend_window = cfg.indicators.detrend_window if detrend_window is None else detrend_window
    args = (sim.dt, sim.sample_every, sim.x0)
    seed_ramp, seed_ctrl = derive_seeds(seed)
    ramp = simulate(
        Ramp(sim.r_start, sim.r_end, duration), sim.sigma, n_ramp, *args, seed=seed_ramp
    )
    ctrl = simulate(
        Ramp.constant(sim.r_start, duration), sim.sigma, n_control, *args, seed=seed_ctrl
    )
    dt_s = ramp.sample_interval
    tip = first_crossing(ramp.x)
    t_fold = duration * FOLD_R / abs(sim.r_end - sim.r_start)
    tip_t = tip * dt_s
    candidates = np.flatnonzero((tip < ramp.n_samples) & (tip_t >= t_fold))
    if candidates.size == 0:
        msg = "no ramp run tips at or after the fold time"
        raise RuntimeError(msg)
    run = int(candidates[np.argmin(tip_t[candidates])])
    x = ramp.x[:, run]
    tip_index = int(tip[run])
    end_index = tip_index - detrend_window

    ind = compute_indicators(x, window, detrend_window)
    var_ramp, ar1_ramp = ind.variance.copy(), ind.ar1.copy()
    var_ramp[end_index + 1 :] = np.nan
    ar1_ramp[end_index + 1 :] = np.nan
    cind = compute_indicators(ctrl.x, window, detrend_window)
    q = (10.0, 50.0, 90.0)
    var_ctrl = np.full((3, len(ramp.t)), np.nan)
    ar1_ctrl = np.full((3, len(ramp.t)), np.nan)
    valid = slice(window - 1, None)  # earlier samples have no full window
    var_ctrl[:, valid] = np.nanpercentile(cind.variance[valid], q, axis=1)
    ar1_ctrl[:, valid] = np.nanpercentile(cind.ar1[valid], q, axis=1)
    var_ctrl[:, end_index + 1 :] = np.nan  # same horizon as the ramp curves
    ar1_ctrl[:, end_index + 1 :] = np.nan
    return RollingData(
        t=ramp.t,
        x=x,
        tip_index=tip_index,
        end_index=end_index,
        var_ramp=var_ramp,
        ar1_ramp=ar1_ramp,
        var_ctrl=var_ctrl,
        ar1_ctrl=ar1_ctrl,
        window_samples=window,
        sample_interval=dt_s,
    )


def _slow_motion_positions(
    n_samples: int,
    n_frames: int,
    focus: int,
    *,
    before: int = 8,
    after: int = 40,
    factor: float = 7.0,
) -> FloatArray:
    """Fractional sample index shown at each of ``n_frames`` frames, slowed around ``focus``.

    Samples in ``[focus - before, focus + after]`` get ``factor`` times more screen time.
    """
    weight = np.ones(n_samples)
    weight[max(focus - before, 0) : focus + after] = factor
    cum = np.concatenate([[0.0], np.cumsum(weight[:-1])])
    return np.asarray(np.interp(np.linspace(0.0, cum[-1], n_frames), cum, np.arange(n_samples)))


def _reveal_box() -> Bbox:
    """Return a unit axes-fraction clip box; set ``box.x1`` to reveal from the left."""
    return Bbox([[0.0, 0.0], [0.0, 1.0]])


def _clip_to_reveal(artists: Sequence[Artist], ax: Axes, box: Bbox) -> None:
    """Clip ``artists`` to the growing axes-fraction ``box``."""
    clip = TransformedBbox(box, ax.transAxes)
    for artist in artists:
        artist.set_clip_box(clip)


@_styled
def animate_rolling_window(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    fps: int = 30,
    duration: float = A3_DURATION,
    width: int = DEFAULT_WIDTH,
    data: RollingData | None = None,
) -> tuple[Path, Path]:
    """Render animation A3: the rolling window sliding over a ramp realization.

    Parameters
    ----------
    lang : {"es", "en"}
        Language of the on-screen text.
    out_dir : pathlib.Path, optional
        Directory for ``a3_rolling_window.mp4`` and ``a3_rolling_window_poster.png``
        (default ``results/animations/<lang>``).
    fps : int, default 30
        Frames per second.
    duration : float, default 19.5
        Clip length in seconds (holds included).
    width : int, default 1920
        Output width in pixels (multiple of 128).
    data : RollingData, optional
        Precomputed series (default :func:`rolling_window_data`).

    Returns
    -------
    tuple of (pathlib.Path, pathlib.Path)
        The MP4 and the poster PNG.
    """
    out = out_dir if out_dir is not None else results_dir() / "animations" / lang
    video, poster = out / "a3_rolling_window.mp4", out / "a3_rolling_window_poster.png"
    d = data if data is not None else rolling_window_data()
    fig, dpi = _new_figure(width)
    n_start, n_motion, n_end = _frame_counts(duration, fps, *A3_HOLDS)

    # Frames -> fractional sample index (hold, slow-motion run until just after the tip, hold).
    last = min(d.tip_index + round(50.0 / d.sample_interval), len(d.t) - 1)
    pos = _slow_motion_positions(last + 1, n_motion, d.tip_index)
    pos_f = np.concatenate([np.zeros(n_start), pos, np.full(n_end, pos[-1])])
    n_frames = len(pos_f)
    t_axis = float(np.ceil(d.t[last] / 100.0) * 100.0)
    dt_s = d.sample_interval
    w_time = d.window_samples * dt_s

    left, wid = 0.125, 0.835
    ax_x = fig.add_axes((left, 0.585, wid, 0.385))
    ax_v = fig.add_axes((left, 0.385, wid, 0.155), sharex=ax_x)
    ax_a = fig.add_axes((left, 0.19, wid, 0.155), sharex=ax_x)
    for ax in (ax_x, ax_v, ax_a):
        style_axes(ax, grid=True)
        ax.tick_params(labelsize=FONT_BASE)
    ax_x.set_xlim(0.0, t_axis)
    for ax in (ax_x, ax_v):
        ax.tick_params(labelbottom=False)
    ax_a.set_xlabel(_text("time_axis", lang), fontsize=FONT_LABEL)
    ax_x.set_ylim(-1.45, 1.6)
    ax_x.set_yticks([-1, 0, 1])
    ax_x.set_ylabel("x", fontsize=FONT_LABEL, rotation=0, labelpad=16)

    # Sliding window band.
    band = Rectangle(
        (0.0, 0.0), 0.0, 1.0, transform=ax_x.get_xaxis_transform(),
        facecolor=PALETTE.ramp_fill, edgecolor=PALETTE.ramp, lw=1.2, zorder=1,
    )  # fmt: skip
    ax_x.add_patch(band)
    win_label = ax_x.text(
        0.0, 0.97, _text("a3_window", lang), transform=ax_x.get_xaxis_transform(),
        fontsize=FONT_BASE, color=PALETTE.ramp, ha="left", va="top",
    )  # fmt: skip
    (line_x,) = ax_x.plot(d.t, d.x, color=PALETTE.ramp, lw=LINE_W, zorder=3)
    (head_x,) = ax_x.plot(
        [], [], ls="none", marker="o", ms=10, color=PALETTE.ramp, mec=PALETTE.background, mew=1.5,
        zorder=4, clip_on=False,
    )  # fmt: skip

    # Indicator panels.
    def indicator_axes(
        ax: Axes, ramp_y: FloatArray, ctrl: FloatArray, label: str, y_top: float
    ) -> tuple[list[Artist], Line2D]:
        band_c = ax.fill_between(d.t, ctrl[0], ctrl[2], color=PALETTE.control_fill, lw=0, zorder=1)
        (med,) = ax.plot(d.t, ctrl[1], color=PALETTE.control, lw=LINE_W, zorder=2)
        (rl,) = ax.plot(d.t, ramp_y, color=PALETTE.ramp, lw=LINE_W + 0.4, zorder=3)
        (hd,) = ax.plot(
            [], [], ls="none", marker="o", ms=10, color=PALETTE.ramp, mec=PALETTE.background,
            mew=1.5, zorder=4, clip_on=False,
        )  # fmt: skip
        ax.set_ylim(0.0, y_top)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=3, prune="lower"))
        ax.set_ylabel(label, fontsize=FONT_LABEL)
        return [band_c, med, rl], hd

    seen = slice(0, last + 1)
    v_top = 1.15 * float(max(np.nanmax(d.var_ramp[seen]), np.nanmax(d.var_ctrl[2][seen])))
    arts_v, head_v = indicator_axes(ax_v, d.var_ramp, d.var_ctrl, _text("a3_variance", lang), v_top)
    arts_a, head_a = indicator_axes(ax_a, d.ar1_ramp, d.ar1_ctrl, _text("a3_ar1", lang), 1.0)
    ax_a.yaxis.set_major_locator(MaxNLocator(nbins=2, prune="lower"))
    _localise_ticks(lang, ax_x, ax_v, ax_a)
    ax_v.text(0.012, 0.9, _text("a3_ramp", lang), transform=ax_v.transAxes, color=PALETTE.ramp,
              fontsize=FONT_BASE, va="top", ha="left")  # fmt: skip
    ax_v.text(
        0.012, 0.55, _text("a3_control", lang), transform=ax_v.transAxes,
        color=PALETTE.control_text, fontsize=FONT_BASE, va="top", ha="left",
    )  # fmt: skip

    box = _reveal_box()
    for ax, arts in ((ax_x, [line_x]), (ax_v, arts_v), (ax_a, arts_a)):
        _clip_to_reveal(arts, ax, box)
    fig.text(
        0.5, 0.012, _text("a3_caption", lang), ha="center", fontsize=FONT_CAPTION, color=PALETTE.ink
    )
    note = ax_a.text(
        0.99, 0.06, _text("a3_note", lang), transform=ax_a.transAxes, fontsize=FONT_NOTE,
        color=PALETTE.muted, ha="right", va="bottom",
    )  # fmt: skip
    note.set_visible(False)

    def update(i: int) -> None:
        s = float(pos_f[i])
        t_now = s * dt_s
        box.x1 = max(min(t_now / t_axis, 1.0), 1e-4)
        band.set_visible(t_now > 0.0)
        win_label.set_visible(t_now > 0.0)
        x0 = max(t_now - w_time, 0.0)
        band.set_x(x0)
        band.set_width(t_now - x0)
        win_label.set_x(x0 + 0.01 * t_axis)
        head_x.set_data([t_now], [float(np.interp(s, np.arange(len(d.t)), d.x))])
        s_ind = min(s, float(d.end_index))
        for head, ramp_y in ((head_v, d.var_ramp), (head_a, d.ar1_ramp)):
            lo = d.window_samples - 1
            if s_ind >= lo:
                head.set_data(
                    [s_ind * dt_s], [float(np.interp(s_ind, np.arange(len(d.t)), ramp_y))]
                )
            else:
                head.set_data([], [])
        note.set_visible(s >= d.end_index)

    poster_frame = int(np.argmax(pos_f >= d.tip_index + 20.0 / dt_s))
    _render(fig, update, n_frames, fps, video, poster, poster_frame, dpi)
    return video, poster


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------
def make_all(lang: Lang, out_dir: Path | None = None, fps: int = 30) -> list[Path]:
    """Render the three animations and their posters.

    Parameters
    ----------
    lang : {"es", "en"}
        Language of the on-screen text.
    out_dir : pathlib.Path, optional
        Base directory; files go to ``out_dir / lang`` (default ``results/animations``).
    fps : int, default 30
        Frames per second.

    Returns
    -------
    list of pathlib.Path
        ``[a1.mp4, a1_poster.png, a2.mp4, a2_poster.png, a3.mp4, a3_poster.png]``.
    """
    base = out_dir if out_dir is not None else results_dir() / "animations"
    target = base / lang
    paths: list[Path] = []
    for video, poster in (
        animate_bifurcation(lang, target, fps=fps),
        animate_noisy_ball(lang, target, fps=fps),
        animate_rolling_window(lang, target, fps=fps),
    ):
        paths.extend([video, poster])
    return paths
