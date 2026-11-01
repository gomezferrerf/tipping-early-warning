"""Shared visual style: pastel backgrounds, deeper line colors, one color per meaning.

The line colors were validated for contrast on the cream background and for
color-vision-deficiency separation. They are only ever paired as
(stable, unstable) and (ramp, control); the two pairs never share a chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

Lang = Literal["es", "en"]


@dataclass(frozen=True)
class Palette:
    """Color tokens. ``*_fill`` are pastel tones for bands and fills only."""

    background: str = "#FBF8F3"
    ink: str = "#2F3A4A"
    muted: str = "#8A93A0"
    grid: str = "#E8E3DA"

    stable: str = "#2A78D6"
    stable_fill: str = "#CFE3F5"
    unstable: str = "#D9622B"
    unstable_fill: str = "#FBD9C6"
    ramp: str = "#6250D6"
    ramp_fill: str = "#E1DBF2"
    control: str = "#159A6C"
    control_fill: str = "#D3EBDD"


PALETTE = Palette()

FONT_FAMILY = ["Inter", "Segoe UI", "Calibri", "DejaVu Sans"]


def apply_style() -> None:
    """Set matplotlib rcParams for the project look (call once per script)."""
    p = PALETTE
    mpl.rcParams.update(
        {
            "figure.facecolor": p.background,
            "savefig.facecolor": p.background,
            "axes.facecolor": p.background,
            "axes.edgecolor": p.muted,
            "axes.labelcolor": p.ink,
            "axes.titlecolor": p.ink,
            "axes.titleweight": "regular",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": p.grid,
            "grid.linewidth": 0.8,
            "text.color": p.ink,
            "xtick.color": p.muted,
            "ytick.color": p.muted,
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FAMILY,
            "font.size": 14,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "legend.frameon": False,
            "legend.fontsize": 13,
            "lines.linewidth": 2.4,
            "savefig.dpi": 200,
        }
    )


def style_axes(ax: Axes, *, grid: bool = True) -> Axes:
    """Apply the minimal axes look (thin recessive spines, optional y grid)."""
    ax.set_facecolor(PALETTE.background)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(PALETTE.muted)
    ax.grid(grid, axis="y", color=PALETTE.grid, linewidth=0.8)
    ax.set_axisbelow(True)
    return ax


def new_figure(width: float = 13.33, height: float = 7.5) -> tuple[plt.Figure, Axes]:
    """Create a 16:9 figure with one styled axes."""
    apply_style()
    fig, ax = plt.subplots(figsize=(width, height))
    style_axes(ax)
    return fig, ax
