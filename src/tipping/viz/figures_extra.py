# ruff: noqa: RUF001  (Greek letters and typographic dashes are intended in figure text)
"""Extra figures: the noise-amplitude confound (backup slide ``b05``).

Colour encoding (one colour, one meaning): the *groups* of the right-hand panels use the deck's
group colours, ``ramp`` (violet: the group whose noise rises) and ``control`` (green: constant
noise). The two *indicators* never use those colours: the variance is a filled ``ink`` marker and
the AR(1) a hollow ``muted`` marker, on the left panel only. Texts live in :data:`_TEXT`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.axes import Axes
from numpy.typing import NDArray

from tipping.confound import RAMP_R_END, IndicatorTraces, indicator_traces
from tipping.paths import results_dir
from tipping.viz.figures import (
    DPI,
    FS_NOTE,
    SIZE_WIDE,
    _axes,
    _fixed,
    _new_figure,
    auc_text,
    styled,
)
from tipping.viz.labels import text
from tipping.viz.style import PALETTE, Lang

FloatArray = NDArray[np.float64]

SIZE = SIZE_WIDE
"""Canvas (inches), the same as the other wide slide figures (2.3:1)."""
SIGMA_END = 0.15
"""Final noise amplitude shown in the figure (three times the baseline 0.05)."""
TRACE_SEED = 1
SUMMARY_FILE = "confound.json"

_TEXT: dict[str, dict[str, str]] = {
    "row_noise": {
        "es": "A · el ruido sube, r = 0\n(σ: {sigma0} → {sigma})",
        "en": "A · noise rises, r = 0\n(σ: {sigma0} → {sigma})",
    },
    "row_fold": {
        "es": "B · el sistema se acerca\na la bifurcación (r: 0 → {r})",
        "en": "B · the system approaches\nthe fold (r: 0 → {r})",
    },
    "variance": {"es": "varianza", "en": "variance"},
    "ar1": {"es": "AR(1)", "en": "AR(1)"},
    "auc_axis": {
        "es": "AUC (rampa frente a control)",
        "en": "AUC (scenario versus control)",
    },
    "chance": {"es": "azar", "en": "chance"},
    "noise_group": {"es": "el ruido sube", "en": "noise rises"},
    "control_group": {"es": "control", "en": "control"},
    "time": {"es": "tiempo", "en": "time"},
}


def _label(key: str, lang: Lang, **fields: object) -> str:
    """Return the figure text ``key`` in ``lang`` from :data:`_TEXT`."""
    template = _TEXT[key][lang]
    return template.format(**fields) if fields else template


def _default_dir(lang: Lang) -> Path:
    return results_dir() / "figures" / lang


def load_summary(path: Path | None = None) -> dict[str, Any]:
    """Read the confound summary written by :func:`tipping.confound.main`.

    Parameters
    ----------
    path : pathlib.Path, optional
        JSON file; default is ``results/confound.json``.

    Returns
    -------
    dict
        The parsed summary.

    Raises
    ------
    FileNotFoundError
        If the file does not exist (run ``python -m tipping.confound`` first).
    """
    source = results_dir() / SUMMARY_FILE if path is None else path
    if not source.is_file():
        msg = f"{source} not found: run `python -m tipping.confound` first"
        raise FileNotFoundError(msg)
    parsed: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    return parsed


def _draw_auc_panel(ax: Axes, summary: dict[str, Any], lang: Lang, sigma_end: float) -> None:
    """Paired dot chart: AUC of variance and AR(1), noise-ramp scenario and fold scenario."""
    rows = (
        (1.45, summary["scenarios"][f"noise_{sigma_end:.2f}"]["pooled"], "row_noise"),
        (0.0, summary["scenarios"]["fold"]["pooled"], "row_fold"),
    )
    offset = 0.17
    sigma0 = _fixed(float(summary["config"]["sigma_start"]), lang)
    fields = {
        "sigma0": sigma0,
        "sigma": _fixed(sigma_end, lang),
        "r": _fixed(RAMP_R_END, lang, 1),
    }
    ax.axvline(0.5, color=PALETTE.muted, lw=1.4, ls=(0, (5, 3)), zorder=1)
    ax.text(
        0.505,
        -0.6,
        _label("chance", lang),
        color=PALETTE.muted,
        fontsize=FS_NOTE,
        va="center",
    )
    for y, pooled, key in rows:
        ax.text(
            0.405,
            y + 0.55,
            _label(key, lang, **fields),
            fontsize=FS_NOTE,
            va="center",
            ha="left",
            linespacing=1.15,
            bbox={"facecolor": PALETTE.background, "edgecolor": "none", "pad": 3.0},
            zorder=3,
        )
        for ind, dy, filled in (("variance", offset, True), ("ar1", -offset, False)):
            entry = pooled[ind]
            auc = float(entry["auc"])
            lo, hi = (float(v) for v in entry["auc_ci95"])
            ypos = y + dy
            ax.plot([lo, hi], [ypos, ypos], color=PALETTE.ink if filled else PALETTE.muted, lw=2.4)
            ax.plot(
                [auc],
                [ypos],
                marker="o",
                markersize=13,
                markeredgewidth=2.6,
                markerfacecolor=PALETTE.ink if filled else PALETTE.background,
                markeredgecolor=PALETTE.ink if filled else PALETTE.muted,
                linestyle="none",
                zorder=4,
            )
            label = f"{_label(ind, lang)}  {auc_text(auc, lang)}"
            # Labels sit left of the dot, except when the dot is near the left edge of the axes.
            left = auc > 0.75
            ax.text(
                auc - 0.03 if left else auc + 0.035,
                ypos,
                label,
                ha="right" if left else "left",
                va="center",
                fontsize=FS_NOTE,
            )
    ax.set_xlim(0.4, 1.03)
    ax.set_ylim(-0.8, 2.35)
    ax.set_yticks([])
    ticks = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    ax.set_xticks(ticks, [_fixed(t, lang, 1) for t in ticks])
    ax.set_xlabel(_label("auc_axis", lang))
    ax.grid(False)
    ax.spines["left"].set_visible(False)


def _draw_trace(
    ax: Axes,
    t: FloatArray,
    noise: FloatArray,
    control: FloatArray,
    *,
    scale: float,
    ylabel: str,
    lang: Lang,
    label_gap: float,
) -> None:
    """Median and 10-90% band of one indicator, noise-ramp group (violet) versus control."""
    for q, color, fill in (
        (control, PALETTE.control, PALETTE.control_fill),
        (noise, PALETTE.ramp, PALETTE.ramp_fill),
    ):
        ax.fill_between(t, q[0] * scale, q[2] * scale, color=fill, lw=0, zorder=1)
        ax.plot(t, q[1] * scale, color=color, lw=2.4, zorder=2)
    x_label = float(t[-1]) + 20.0
    for q, color, key, shift in (
        (noise, PALETTE.ramp, "noise_group", label_gap),
        (control, PALETTE.control, "control_group", -label_gap),
    ):
        ax.text(
            x_label,
            float(q[1, -1]) * scale + shift,
            _label(key, lang),
            color=color,
            va="center",
            fontsize=FS_NOTE,
        )
    ax.set_xlim(float(t[0]), float(t[-1]) + 330.0)
    ax.set_ylabel(ylabel)


@styled
def make_confound_figure(
    lang: Lang,
    out_dir: Path | None = None,
    *,
    summary: dict[str, Any] | None = None,
    traces: IndicatorTraces | None = None,
    sigma_end: float = SIGMA_END,
) -> Path:
    """Draw the noise-confound figure and save it as ``b05_noise_confound.png``.

    Left: AUC of the Kendall tau of the variance (filled ink dot) and of the AR(1) (hollow muted
    dot) with bootstrap 95% intervals, for scenario A (noise rises at constant ``r = 0``) and
    scenario B (the baseline approach to the fold). Right: median rolling variance (top) and
    rolling AR(1) (bottom) over time with the 10-90% band, noise-ramp group (violet) versus
    control (green).

    Parameters
    ----------
    lang : {"es", "en"}
        Language of the figure text.
    out_dir : pathlib.Path, optional
        Output directory; default is ``results/figures/<lang>``.
    summary : dict, optional
        Parsed ``confound.json``; read from ``results/`` if omitted.
    traces : IndicatorTraces, optional
        Indicator percentiles over time; simulated with
        :func:`tipping.confound.indicator_traces` (300 runs, seed 1) if omitted.
    sigma_end : float, default 0.15
        Final noise amplitude of the noise-ramp scenario shown (must be in the summary).

    Returns
    -------
    pathlib.Path
        Path of the PNG file.
    """
    data = load_summary() if summary is None else summary
    tr = indicator_traces(sigma_end, seed=TRACE_SEED) if traces is None else traces

    fig = _new_figure(*SIZE)
    grid = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.08])
    ax_auc = _axes(fig, lang, grid[:, 0])
    ax_var = _axes(fig, lang, grid[0, 1], grid=True)
    ax_ar1 = _axes(fig, lang, grid[1, 1], grid=True, sharex=ax_var)

    _draw_auc_panel(ax_auc, data, lang, sigma_end)
    _draw_trace(
        ax_var,
        tr.t,
        tr.variance_noise,
        tr.variance_control,
        scale=1e3,
        ylabel=text("rolling_variance", lang).replace(" (", "\n("),  # two lines: fits the height
        lang=lang,
        label_gap=0.0,
    )
    _draw_trace(
        ax_ar1,
        tr.t,
        tr.ar1_noise,
        tr.ar1_control,
        scale=1.0,
        ylabel=text("rolling_ar1", lang),
        lang=lang,
        label_gap=0.06,
    )
    ax_ar1.set_ylim(0.0, 0.8)
    ax_ar1.set_xticks([200, 400, 600, 800, 1000, 1200])
    ax_var.tick_params(labelbottom=False)
    ax_ar1.set_xlabel(_label("time", lang))

    out = _default_dir(lang) if out_dir is None else out_dir
    out.mkdir(parents=True, exist_ok=True)
    path = out / "b05_noise_confound.png"
    fig.savefig(path, dpi=DPI, facecolor=PALETTE.background)
    return path
