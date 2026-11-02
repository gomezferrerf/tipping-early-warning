"""Parquet input/output helpers and DuckDB queries over result tables."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import duckdb
import pandas as pd


def write_parquet(df: pd.DataFrame, path: Path | str) -> Path:
    """Write a DataFrame to Parquet atomically.

    The table is first written to a temporary file in the destination directory and then moved
    over the destination with :func:`os.replace`, so a reader never sees a half-written file
    and an interrupted write leaves any previous file intact. Missing parent directories are
    created and an existing file is overwritten.

    Parameters
    ----------
    df : pandas.DataFrame
        Table to write (the index is not stored).
    path : pathlib.Path or str
        Destination file.

    Returns
    -------
    pathlib.Path
        The destination path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    os.close(handle)  # Windows cannot replace a file that is still open
    tmp = Path(tmp_name)
    try:
        df.to_parquet(tmp, engine="pyarrow", index=False)
        if os.name == "posix":  # mkstemp creates the file as 0600; use the umask default instead
            umask = os.umask(0)
            os.umask(umask)
            tmp.chmod(0o666 & ~umask)
        tmp.replace(target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return target


def read_parquet(path: Path | str) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame.

    Parameters
    ----------
    path : pathlib.Path or str
        Parquet file.

    Returns
    -------
    pandas.DataFrame
        The stored table.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    """
    source = Path(path)
    if not source.is_file():
        msg = f"Parquet file not found: {source}"
        raise FileNotFoundError(msg)
    return pd.read_parquet(source, engine="pyarrow")


def query(parquet_path: Path | str, sql: str, table: str = "data") -> pd.DataFrame:
    """Run a DuckDB SQL query over a Parquet file.

    The file is exposed to the query as a table called ``table`` (default ``data``).

    Parameters
    ----------
    parquet_path : pathlib.Path or str
        Parquet file to query.
    sql : str
        SQL statement referring to the table by name, e.g.
        ``"SELECT sigma, avg(auc_ar1) AS auc FROM data GROUP BY sigma ORDER BY sigma"``.
    table : str, default "data"
        Name under which the file is visible in ``sql``.

    Returns
    -------
    pandas.DataFrame
        Query result.

    Raises
    ------
    FileNotFoundError
        If ``parquet_path`` does not exist.
    """
    source = Path(parquet_path)
    if not source.is_file():
        msg = f"Parquet file not found: {source}"
        raise FileNotFoundError(msg)
    connection = duckdb.connect(":memory:")
    try:
        connection.register(table, pd.read_parquet(source, engine="pyarrow"))
        return connection.execute(sql).df()
    finally:
        connection.close()
