"""Tests for the sweep: grid, seeds, schema, determinism and summary."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from tipping.config import SweepConfig, load_sweep_config
from tipping.io import query, read_parquet
from tipping.sweep import (
    SUMMARY_COLUMNS,
    SWEEP_COLUMNS,
    Cell,
    build_grid,
    cell_seed,
    default_sweep_config_path,
    resolve_n_jobs,
    run_cell,
    run_sweep,
    summarise,
)

SMALL = {
    "sigmas": [0.05, 0.15],
    "durations": [100, 200],
    "seeds": [1, 2],
    "n_runs": 20,
    "n_boot": 50,
    "n_jobs": 1,
}


def _write_config(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "sweep.yaml"
    path.write_text(yaml.safe_dump({**SMALL, **overrides}), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def small_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("sweep")
    return run_sweep(_write_config(tmp), tmp / "out")


def test_default_sweep_config_values() -> None:
    cfg = load_sweep_config(default_sweep_config_path())
    assert cfg.sigmas == [0.03, 0.05, 0.10, 0.15, 0.30]
    assert cfg.durations == [100, 200, 400, 1000, 2000]
    assert cfg.n_runs == 300
    assert cfg.seeds == [1, 2, 3]
    assert len(build_grid(cfg)) == 75


def test_grid_is_sorted_and_complete() -> None:
    cfg = SweepConfig(sigmas=[0.1, 0.05], durations=[200.0, 100.0], seeds=[2, 1])
    grid = build_grid(cfg)
    assert len(grid) == 8
    assert grid == sorted(grid, key=lambda c: (c.sigma, c.duration, c.seed))
    assert grid[0] == Cell(0.05, 100.0, 1)


def test_window_rule_is_derived_per_cell() -> None:
    cfg = SweepConfig()
    expected = {100.0: 20, 200.0: 40, 400.0: 80, 1000.0: 200, 2000.0: 400}
    for duration, window in expected.items():
        ind = cfg.indicator_config(duration)
        assert ind.window == max(10, round(0.10 * duration / 0.5)) == window
        assert ind.detrend_window == max(5, window // 4)
    short = cfg.indicator_config(20.0)  # 0.1 * 40 samples = 4 -> floored at 10
    assert (short.window, short.detrend_window) == (10, 5)


def test_cell_seed_depends_only_on_the_cell() -> None:
    a = Cell(0.05, 100.0, 1)
    assert cell_seed(a) == cell_seed(Cell(0.05, 100.0, 1))
    others = [Cell(0.15, 100.0, 1), Cell(0.05, 200.0, 1), Cell(0.05, 100.0, 2)]
    assert len({cell_seed(a), *map(cell_seed, others)}) == 4


def test_resolve_n_jobs() -> None:
    assert resolve_n_jobs(1, 10) == 1
    assert resolve_n_jobs(8, 3) == 3
    assert resolve_n_jobs(-1, 1000) >= 1
    assert resolve_n_jobs(None, 1000) >= 1


def test_run_cell_row_has_the_schema() -> None:
    cfg = SweepConfig(n_runs=20)
    row = run_cell(cfg, Cell(0.05, 100.0, 1))
    assert tuple(row) == SWEEP_COLUMNS
    assert row["window"] == 20
    assert row["n_runs"] == 20
    assert 0.0 <= float(row["auc_ar1"]) <= 1.0


def test_sweep_table_schema(small_run: Path) -> None:
    assert small_run.name == "sweep.parquet"
    df = read_parquet(small_run)
    assert tuple(df.columns) == SWEEP_COLUMNS
    assert len(df) == 8
    assert not df.duplicated(["sigma", "duration", "seed"]).any()
    assert set(df["window"]) == {20, 40}
    assert (df["n_runs"] == 20).all()
    for col in ("frac_ramp_tipped_early", "frac_null_tipped"):
        assert df[col].between(0.0, 1.0).all()
    assert (df[["n_valid_ramp", "n_valid_null"]] <= 20).all().all()


def test_summary_table_schema_and_ci_brackets_mean(small_run: Path) -> None:
    summary = read_parquet(small_run.with_name("sweep_summary.parquet"))
    assert tuple(summary.columns) == SUMMARY_COLUMNS
    assert len(summary) == 4
    assert (summary["n_seeds"] == 2).all()
    for metric in ("auc_var", "auc_ar1", "tpr_var", "tpr_ar1"):
        ok = summary[metric + "_mean"].notna()
        assert ok.all()
        assert (summary[metric + "_ci_lo"] <= summary[metric + "_mean"] + 1e-12).all()
        assert (summary[metric + "_mean"] <= summary[metric + "_ci_hi"] + 1e-12).all()


def test_summary_matches_hand_computation() -> None:
    sweep = pd.DataFrame(
        {
            "sigma": [0.05] * 3,
            "duration": [100.0] * 3,
            "seed": [1, 2, 3],
            "n_runs": [10] * 3,
            "window": [20] * 3,
            "auc_var": [0.6, 0.7, 0.8],
            "auc_ar1": [0.5, np.nan, 0.7],
            "tpr_var": [0.1, 0.2, 0.3],
            "tpr_ar1": [np.nan] * 3,
            "frac_ramp_tipped_early": [0.0, 0.5, 1.0],
            "frac_null_tipped": [0.0, 0.0, 0.3],
            "n_valid_ramp": [10, 8, 6],
            "n_valid_null": [10, 10, 10],
        }
    )
    out = summarise(sweep, n_boot=200).iloc[0]
    assert out["auc_var_mean"] == pytest.approx(0.7)
    assert out["auc_ar1_mean"] == pytest.approx(0.6)  # nan ignored
    assert np.isnan(out["tpr_ar1_mean"])
    assert 0.6 - 1e-9 <= out["auc_var_ci_lo"] <= 0.7 <= out["auc_var_ci_hi"] <= 0.8 + 1e-9
    assert out["frac_ramp_tipped_early"] == pytest.approx(0.5)
    assert out["n_valid_ramp"] == pytest.approx(8.0)


def test_determinism_across_n_jobs(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, seeds=[1], sigmas=[0.05, 0.15], durations=[100, 200])
    serial = read_parquet(run_sweep(cfg, tmp_path / "a", n_jobs=1))
    parallel = read_parquet(run_sweep(cfg, tmp_path / "b", n_jobs=2))
    pd.testing.assert_frame_equal(serial, parallel)
    pd.testing.assert_frame_equal(
        read_parquet(tmp_path / "a" / "sweep_summary.parquet"),
        read_parquet(tmp_path / "b" / "sweep_summary.parquet"),
    )


def test_results_do_not_depend_on_the_rest_of_the_grid(tmp_path: Path) -> None:
    full = read_parquet(run_sweep(_write_config(tmp_path), tmp_path / "full"))
    sub_cfg = _write_config(tmp_path, sigmas=[0.15], durations=[200], seeds=[2])
    sub = read_parquet(run_sweep(sub_cfg, tmp_path / "sub"))
    match = full[(full["sigma"] == 0.15) & (full["duration"] == 200.0) & (full["seed"] == 2)]
    pd.testing.assert_frame_equal(sub, match.reset_index(drop=True))


def test_seeds_are_independent_replications(small_run: Path) -> None:
    df = read_parquet(small_run)
    for _, group in df.groupby(["sigma", "duration"]):
        by_seed = group.set_index("seed")
        assert not np.allclose(
            by_seed.loc[1, ["auc_var", "auc_ar1", "tpr_var", "tpr_ar1"]].to_numpy(dtype=float),
            by_seed.loc[2, ["auc_var", "auc_ar1", "tpr_var", "tpr_ar1"]].to_numpy(dtype=float),
        )


def test_rerun_overwrites_and_is_idempotent(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, seeds=[1], sigmas=[0.05], durations=[100])
    first = read_parquet(run_sweep(cfg, tmp_path))
    second = read_parquet(run_sweep(cfg, tmp_path))
    pd.testing.assert_frame_equal(first, second)
    assert sorted(p.name for p in tmp_path.glob("*.parquet")) == [
        "sweep.parquet",
        "sweep_summary.parquet",
    ]


def test_sweep_output_is_queryable_with_duckdb(small_run: Path) -> None:
    out = query(
        small_run,
        "SELECT sigma, duration, avg(auc_ar1) AS auc FROM data "
        "GROUP BY sigma, duration ORDER BY sigma, duration",
    )
    assert len(out) == 4
    assert out["auc"].between(0.0, 1.0).all()
