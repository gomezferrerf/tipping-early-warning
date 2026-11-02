"""Tests for the Parquet and DuckDB helpers."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tipping.io import query, read_parquet, write_parquet


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sigma": [0.05, 0.05, 0.15, 0.15],
            "duration": [100.0, 200.0, 100.0, 200.0],
            "auc": [0.6, 0.9, 0.55, 0.8],
            "n": np.array([1, 2, 3, 4], dtype=np.int64),
        }
    )


def test_round_trip_preserves_values_and_dtypes(tmp_path: Path, frame: pd.DataFrame) -> None:
    path = write_parquet(frame, tmp_path / "t.parquet")
    pd.testing.assert_frame_equal(read_parquet(path), frame)


def test_write_creates_parent_directories(tmp_path: Path, frame: pd.DataFrame) -> None:
    path = write_parquet(frame, tmp_path / "a" / "b" / "t.parquet")
    assert path.is_file()


def test_write_overwrites_and_leaves_no_temporary_files(
    tmp_path: Path, frame: pd.DataFrame
) -> None:
    target = tmp_path / "t.parquet"
    write_parquet(frame, target)
    write_parquet(frame.iloc[:2], target)
    assert len(read_parquet(target)) == 2
    assert [p.name for p in tmp_path.iterdir()] == ["t.parquet"]


def test_failed_write_keeps_previous_file(
    tmp_path: Path, frame: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t.parquet"
    write_parquet(frame, target)
    before = target.read_bytes()

    def boom(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        write_parquet(frame.iloc[:1], target)
    assert target.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["t.parquet"]


def test_read_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_parquet(tmp_path / "missing.parquet")
    with pytest.raises(FileNotFoundError):
        query(tmp_path / "missing.parquet", "SELECT 1")


def test_duckdb_query_round_trip(tmp_path: Path, frame: pd.DataFrame) -> None:
    path = write_parquet(frame, tmp_path / "t.parquet")
    out = query(
        path,
        "SELECT sigma, avg(auc) AS mean_auc, count(*) AS cells "
        "FROM data GROUP BY sigma ORDER BY sigma",
    )
    assert list(out["sigma"]) == [0.05, 0.15]
    np.testing.assert_allclose(out["mean_auc"], [0.75, 0.675])
    assert list(out["cells"]) == [2, 2]


def test_query_custom_table_name(tmp_path: Path, frame: pd.DataFrame) -> None:
    path = write_parquet(frame, tmp_path / "t.parquet")
    out = query(path, "SELECT max(n) AS m FROM sweep", table="sweep")
    assert int(out["m"].iloc[0]) == 4


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_written_file_follows_the_umask(tmp_path: Path, frame: pd.DataFrame) -> None:
    """mkstemp creates 0600 files; the output must get the usual umask-based mode instead."""
    umask = os.umask(0o022)
    try:
        path = write_parquet(frame, tmp_path / "t.parquet")
    finally:
        os.umask(umask)
    assert path.stat().st_mode & 0o777 == 0o644
