"""Tests for the animation module (short low-resolution clips only)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pytest

from tipping.model import FOLD_R, upper_branch
from tipping.viz import animations as anim

LOW_RES = 384  # 384 x 216 pixels; keeps the smoke tests fast


def _probe(path: Path) -> str:
    """Return the stream description printed by ``ffmpeg -i``."""
    proc = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stderr


def _check_clip(video: Path, poster: Path) -> None:
    assert video.is_file()
    assert video.stat().st_size > 0
    assert poster.is_file()
    assert poster.stat().st_size > 0
    info = _probe(video)
    assert "h264" in info
    assert "yuv420p" in info
    assert re.search(rf"{LOW_RES}x{LOW_RES * 9 // 16}", info)


def test_text_has_both_languages_for_every_key() -> None:
    assert anim._TEXT
    for key, entry in anim._TEXT.items():
        assert set(entry) == {"es", "en"}, key
        assert entry["es"].strip(), key
        assert entry["en"].strip(), key


def test_bifurcation_smoke(tmp_path: Path) -> None:
    video, poster = anim.animate_bifurcation("en", tmp_path, duration=1.0, width=LOW_RES)
    _check_clip(video, poster)


def test_noisy_ball_smoke(tmp_path: Path) -> None:
    video, poster = anim.animate_noisy_ball("es", tmp_path, duration=1.0, width=LOW_RES)
    _check_clip(video, poster)


def test_rolling_window_smoke(tmp_path: Path) -> None:
    # Smaller batches keep this fast; the selection logic is the same as in production.
    data = anim.rolling_window_data(n_ramp=30, n_control=20)
    video, poster = anim.animate_rolling_window(
        "en", tmp_path, duration=1.0, width=LOW_RES, data=data
    )
    _check_clip(video, poster)


def test_invalid_width_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="multiple of 128"):
        anim.animate_bifurcation("en", tmp_path, duration=1.0, width=1000)


def test_noisy_ball_realization_does_not_tip() -> None:
    tr = anim.noisy_ball_realization()
    x = tr.x[:, 0]
    assert float(np.min(x)) > anim.A2_MIN_X
    assert tr.r[0] == 0.0
    assert tr.r[-1] == pytest.approx(anim.A2_R_END)
    assert tr.r[-1] > -FOLD_R  # the run stays before the fold


def test_noisy_ball_jitter_grows_as_the_valley_flattens() -> None:
    tr = anim.noisy_ball_realization()
    resid = tr.x[:, 0] - upper_branch(tr.r)
    quarter = len(resid) // 4
    assert resid[-quarter:].std() > 1.3 * resid[:quarter].std()


def test_deterministic_fall_tracks_valley_then_tips_at_the_fold() -> None:
    traj = anim.deterministic_fall()
    before = traj.r > -0.35
    assert np.max(np.abs(traj.x[before] - upper_branch(traj.r[before]))) < 0.05
    tipped = int(np.argmax(traj.x < 0.0))
    assert tipped > 0
    r_fall = float(traj.r[tipped])
    assert -FOLD_R - 0.15 < r_fall < -FOLD_R  # falls shortly after the fold (bifurcation delay)
    assert traj.x[-1] < -1.0  # settled in the left valley


def test_rolling_window_data_picks_a_run_tipping_near_the_fold() -> None:
    data = anim.rolling_window_data(n_ramp=30, n_control=20)
    sim = anim.baseline_config().sim
    t_fold = sim.duration * FOLD_R / abs(sim.r_end - sim.r_start)
    tip_t = data.tip_index * data.sample_interval
    assert t_fold <= tip_t < t_fold + 150.0
    assert data.end_index == data.tip_index - anim.baseline_config().indicators.detrend_window
    assert np.isnan(data.var_ramp[data.end_index + 1 :]).all()
    # The indicators grow towards the fold; the control median does not.
    lo, hi = anim.baseline_config().indicators.window, data.end_index
    assert data.ar1_ramp[hi] > data.ar1_ramp[lo] + 0.2
    assert data.var_ramp[hi] > 2.0 * data.var_ramp[lo]
    assert abs(data.ar1_ctrl[1, hi] - data.ar1_ctrl[1, lo]) < 0.1
