"""Compute every number quoted in the talk and write ``results/key_numbers.json``.

Single source of truth for the slides and the speech script: nothing is typed by hand.
Run with ``uv run python -m tipping.key_numbers`` after ``tipping sweep``.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from tipping.config import load_config
from tipping.evaluate import bootstrap_ci, run_experiment, tpr_at_fpr
from tipping.model import FOLD_R
from tipping.paths import default_config_path, results_dir


def _baseline() -> dict[str, Any]:
    cfg = load_config(default_config_path())
    exp = run_experiment(cfg.sim, cfg.indicators, cfg.sim.seed)
    res = exp.result
    x = exp.ramp.x  # (n_samples, n_runs)
    t = exp.ramp.t
    tipped = (x < 0).any(axis=0)
    first = np.argmax(x < 0, axis=0)
    tip_time = t[first[tipped]]
    fold_idx = int(np.argmax(exp.ramp.r <= -FOLD_R))
    out: dict[str, Any] = {
        "seed": cfg.sim.seed,
        "sigma": cfg.sim.sigma,
        "duration": cfg.sim.duration,
        "n_runs": cfg.sim.n_runs,
        "fold_r": FOLD_R,
        "fold_time": float(t[fold_idx]),
        "median_tip_time": float(np.median(tip_time)),
        "frac_ramp_tipped_ever": float(tipped.mean()),
        "auc_ar1": res.auc_ar1,
        "auc_var": res.auc_var,
        "tpr_ar1": res.tpr_ar1,
        "tpr_var": res.tpr_var,
        "frac_ramp_tipped_early": res.frac_ramp_tipped_early,
        "frac_null_tipped": res.frac_null_tipped,
        "n_valid_ramp": res.n_valid_ramp,
        "n_valid_null": res.n_valid_null,
        "median_tau_ramp_ar1": float(np.median(res.tau_ramp_ar1)),
        "median_tau_ramp_var": float(np.median(res.tau_ramp_var)),
        "median_tau_null_ar1": float(np.median(res.tau_null_ar1)),
        "median_tau_null_var": float(np.median(res.tau_null_var)),
        "tau_ar1_fpr5_threshold": float(np.quantile(res.tau_null_ar1, 0.95)),
    }
    lo, hi = bootstrap_ci(res.tau_ramp_ar1, res.tau_null_ar1, seed=0)
    out["auc_ar1_ci95"] = [lo, hi]
    lo, hi = bootstrap_ci(res.tau_ramp_var, res.tau_null_var, seed=0)
    out["auc_var_ci95"] = [lo, hi]
    lo, hi = bootstrap_ci(res.tau_ramp_ar1, res.tau_null_ar1, statistic=tpr_at_fpr, seed=0)
    out["tpr_ar1_ci95"] = [lo, hi]
    return out


def _sweep() -> dict[str, Any]:
    summary = pd.read_parquet(results_dir() / "sweep_summary.parquet")
    return {"columns": list(summary.columns), "rows": json.loads(summary.to_json(orient="records"))}


def main() -> None:
    """Write the JSON file and print it."""
    data = {"baseline": _baseline(), "sweep_summary": _sweep()}
    path = results_dir() / "key_numbers.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data["baseline"], indent=2))
    print(data["sweep_summary"]["columns"])
    print(f"written {path}")


if __name__ == "__main__":
    main()
