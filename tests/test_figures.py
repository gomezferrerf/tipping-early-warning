# ruff: noqa: RUF001
"""Tests for the static figures: label completeness, PNG output, heatmap on synthetic data."""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.image import imread

from tipping.viz import figures as fig
from tipping.viz.labels import LABELS, LANGS, text
from tipping.viz.style import Lang

SMALL = 6  # runs per group in the tests


def _synthetic_summary() -> pd.DataFrame:
    """Summary table with the sweep schema on a 3 x 3 grid; the noisiest row is unreliable."""
    rows = []
    for i, sigma in enumerate((0.05, 0.15, 0.30)):
        for j, duration in enumerate((100.0, 400.0, 2000.0)):
            rows.append(
                {
                    "sigma": sigma,
                    "duration": duration,
                    "auc_ar1_mean": 0.5 + 0.15 * j - 0.04 * i,
                    "auc_var_mean": 0.55 + 0.15 * j - 0.04 * i,
                    "frac_null_tipped": 0.0 if i < 2 else 0.1 + 0.4 * j,
                    "frac_ramp_tipped_early": 0.1 * i * (j + 1),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def baseline() -> fig.Baseline:
    """A reduced baseline experiment shared by the result figures."""
    return fig.compute_baseline(n_runs=SMALL)


def _assert_png(path: Path) -> None:
    assert path.is_file()
    assert path.stat().st_size > 5_000
    image = imread(path)
    assert image.ndim == 3
    assert image.shape[1] > image.shape[0] * 1.1  # wide canvases only


@pytest.mark.parametrize("lang", LANGS)
def test_every_label_has_both_languages(lang: Lang) -> None:
    for key, translations in LABELS.items():
        assert set(translations) == set(LANGS), key
        assert translations[lang].strip(), f"{key} is empty in {lang}"


def test_spanish_labels_use_decimal_commas() -> None:
    assert not [k for k, t in LABELS.items() if re.search(r"\d\.\d", t["es"])], "es uses ','"
    assert fig._fixed(-2.0, "es") == "−2,00"
    assert fig._fixed(-2.0, "en") == "−2.00"
    assert fig._short(-0.385, "es") == "−0,385"
    assert fig._tick(0.25, "es") == "0,25"
    assert fig._tick(-1.0, "en") == "−1"


def test_spanish_never_says_colapso() -> None:
    assert not [key for key, t in LABELS.items() if "colapso" in t["es"].lower()]
    assert not [key for key, t in LABELS.items() if "collapse" in t["en"].lower()]


def test_text_formats_placeholders_and_rejects_unknown_keys() -> None:
    assert text("auc", "es", auc="0.99") == "AUC = 0.99"
    with pytest.raises(KeyError, match="no_such_key"):
        text("no_such_key", "en")


@pytest.mark.parametrize("lang", LANGS)
def test_static_equilibrium_figures(lang: Lang, tmp_path: Path) -> None:
    for make in (fig.fig_landscapes, fig.fig_bifurcation, fig.fig_hysteresis, fig.fig_noise):
        _assert_png(make(lang, tmp_path))
    _assert_png(fig.readme_bifurcation(lang, tmp_path))


def test_hook_and_experiment_figures(tmp_path: Path) -> None:
    _assert_png(fig.fig_hook("es", tmp_path, n_runs=SMALL))
    _assert_png(fig.fig_experiment("es", tmp_path, n_runs=SMALL))


@pytest.mark.parametrize("lang", LANGS)
def test_signal_figure(lang: Lang, tmp_path: Path) -> None:
    path = fig.fig_signal(lang, tmp_path, n_runs=20, duration=150.0)
    assert path.name == "s10_signal.png"
    _assert_png(path)
    titled = fig.fig_signal(lang, tmp_path, n_runs=20, duration=150.0, title=True, filename="t.png")
    _assert_png(titled)


def test_result_figures(baseline: fig.Baseline, tmp_path: Path) -> None:
    _assert_png(fig.fig_results("es", baseline, tmp_path))
    _assert_png(fig.fig_control("en", baseline, tmp_path))
    _assert_png(fig.readme_results("en", baseline, tmp_path, n_runs=SMALL))


@pytest.mark.parametrize("lang", LANGS)
def test_heatmaps_on_synthetic_summary(lang: Lang, tmp_path: Path) -> None:
    summary = _synthetic_summary()
    _assert_png(fig.fig_heatmap(lang, tmp_path, summary=summary))
    _assert_png(fig.fig_heatmap(lang, tmp_path, summary=summary, title=True, filename="h.png"))
    _assert_png(fig.fig_tipped(lang, tmp_path, summary=summary))


def test_pivot_orders_sigma_and_duration_ascending() -> None:
    shuffled = _synthetic_summary().sample(frac=1.0, random_state=0)
    table = fig._pivot(shuffled, "auc_ar1")
    assert list(table.index) == sorted(table.index)
    assert list(table.columns) == sorted(table.columns)
    assert table.at[0.05, 100.0] == pytest.approx(0.5)


def test_unreliable_cells_follow_the_control_tip_rule() -> None:
    flags = fig._pivot(_synthetic_summary(), "frac_null_tipped") > fig.HEATMAP_TIPPED_LIMIT
    assert not flags.loc[0.05].any()
    assert flags.at[0.30, 400.0]
    assert flags.at[0.30, 2000.0]
    assert not flags.at[0.30, 100.0]  # 0.1 is below the 0.2 limit


def test_early_tip_cells_follow_the_survivor_bias_rule() -> None:
    flags = fig._pivot(_synthetic_summary(), "frac_ramp_tipped_early") > fig.HEATMAP_EARLY_LIMIT
    assert not flags.at[0.05, 2000.0]  # 0.0
    assert flags.at[0.30, 2000.0]  # 0.2 * 3 = 0.6
    assert not flags.at[0.15, 100.0]  # 0.1


def test_summary_columns_accept_plain_or_mean_names() -> None:
    plain = _synthetic_summary().rename(columns={"auc_ar1_mean": "auc_ar1"})
    assert fig._column(plain, "auc_ar1") == "auc_ar1"
    with pytest.raises(KeyError, match="auc_missing"):
        fig._column(plain, "auc_missing")


def test_missing_sweep_raises_a_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.parquet"
    with pytest.raises(FileNotFoundError, match="tipping sweep"):
        fig.fig_heatmap("en", tmp_path, sweep_path=missing)
    with pytest.raises(FileNotFoundError, match="tipping sweep"):
        fig.make_all("en", tmp_path, missing)


def test_example_runs_are_seeded_and_ramp_tips() -> None:
    first = fig.example_runs(SMALL)
    second = fig.example_runs(SMALL)
    np.testing.assert_array_equal(first.ramp, second.ramp)
    assert first.ramp[0] == pytest.approx(1.0)
    assert first.ramp[-1] < 0.0 < first.control[-1]  # ramp fell, control did not
    assert first.fold_time == pytest.approx(1283.0, abs=1.0)


def test_valley_data_matches_linear_theory_at_small_noise() -> None:
    steep = fig.valley_data(0.0, sigma=0.02, n_runs=40, duration=200.0)
    assert steep.x_star == pytest.approx(1.0)
    assert steep.rate == pytest.approx(-2.0)
    pooled = steep.deviation[:, steep.kept]
    assert pooled.var() == pytest.approx(0.02**2 / 4.0, rel=0.1)


def test_indicator_bands_ignore_samples_after_the_tip(baseline: fig.Baseline) -> None:
    exp = baseline.experiment
    bands = fig.indicator_bands(exp.ramp.x, exp.ramp.t, baseline.cfg.indicators)
    assert bands.variance.shape[0] == 3
    assert np.all(bands.t <= 1200.0)
    finite = np.isfinite(bands.ar1[1])
    assert finite.any()
    assert np.all(bands.ar1[0][finite] <= bands.ar1[1][finite])
    assert np.all(bands.ar1[1][finite] <= bands.ar1[2][finite])


def test_make_all_writes_expected_files(
    baseline: fig.Baseline, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_path = tmp_path / "sweep_summary.parquet"
    _synthetic_summary().to_parquet(summary_path)
    assets = tmp_path / "assets"
    monkeypatch.setattr(fig, "assets_dir", lambda: assets)
    monkeypatch.setattr(fig, "compute_baseline", lambda: baseline)
    # Shrink the slow simulations inside make_all (module globals are looked up at call time).
    monkeypatch.setattr(fig, "fig_signal", partial(fig.fig_signal, n_runs=20, duration=150.0))
    monkeypatch.setattr(fig, "fig_hook", partial(fig.fig_hook, n_runs=SMALL))
    monkeypatch.setattr(fig, "fig_experiment", partial(fig.fig_experiment, n_runs=SMALL))
    monkeypatch.setattr(fig, "readme_results", partial(fig.readme_results, n_runs=SMALL))
    written = fig.make_all("en", tmp_path / "out", summary_path)
    names = {p.name for p in written}
    assert {"s01_hook.png", "s04_landscapes.png", "s14_heatmap.png", "b04_tipped.png"} <= names
    assert {"fig_bifurcation.png", "fig_signal.png", "fig_results.png", "fig_heatmap.png"} <= names
    assert all(p.is_file() for p in written)
    assert (tmp_path / "out" / "en" / "s10_signal.png").is_file()
    assert (assets / "fig_heatmap.png").is_file()
