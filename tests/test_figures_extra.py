"""Tests for the extra figures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import numpy as np
import pytest

from tipping.confound import IndicatorTraces
from tipping.viz.figures_extra import _TEXT, make_confound_figure
from tipping.viz.style import Lang


def _indicator(auc: float) -> dict[str, Any]:
    return {"auc": auc, "auc_ci95": [auc - 0.02, min(auc + 0.02, 1.0)]}


def _summary() -> dict[str, Any]:
    pooled_noise = {"variance": _indicator(1.0), "ar1": _indicator(0.5)}
    pooled_fold = {"variance": _indicator(1.0), "ar1": _indicator(0.99)}
    return {
        "config": {"sigma_start": 0.05},
        "scenarios": {
            "noise_0.15": {"pooled": pooled_noise},
            "fold": {"pooled": pooled_fold},
        },
    }


def _traces() -> IndicatorTraces:
    t = np.linspace(200.0, 1200.0, 50)

    def band(level: float, slope: float) -> np.ndarray:
        mid = level + slope * (t - t[0]) / 1000.0
        return np.vstack([mid * 0.9, mid, mid * 1.1])

    return IndicatorTraces(
        t=t,
        variance_noise=band(0.0008, 0.002),
        ar1_noise=band(0.35, 0.0),
        variance_control=band(0.0006, 0.0),
        ar1_control=band(0.35, 0.0),
        sigma_end=0.15,
    )


def test_text_has_both_languages() -> None:
    """Every label exists in Spanish and English."""
    assert all(set(v) == {"es", "en"} for v in _TEXT.values())


@pytest.mark.parametrize("lang", ["es", "en"])
def test_confound_figure_is_written(lang: Lang, tmp_path: Path) -> None:
    """The PNG is written at 200 dpi on an 11.5 x 5.0 in canvas."""
    path = make_confound_figure(lang, tmp_path, summary=_summary(), traces=_traces())
    assert path == tmp_path / "b05_noise_confound.png"
    image = mpimg.imread(path)
    assert image.shape[:2] == (1000, 2300)
