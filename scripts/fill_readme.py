"""Fill the RESULTS block of ``README.md`` from the files in ``results/``.

Every number comes from ``results/key_numbers.json``, ``results/sweep_summary.parquet`` or
``results/confound.json``; the sentences only pick words ("higher", "lower") by comparing those
numbers. Run it after ``uv run tipping reproduce``::

    uv run python scripts/fill_readme.py          # rewrite the block in README.md
    uv run python scripts/fill_readme.py --check  # exit 1 if README.md is out of date
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from tipping.config import load_sweep_config
from tipping.paths import project_root, results_dir
from tipping.sweep import default_sweep_config_path

START = "<!-- RESULTS:START -->"
END = "<!-- RESULTS:END -->"


def num(value: float, digits: int = 2) -> str:
    """Format ``value`` with ``digits`` decimals, never rounding a value below 1 up to ``1.00``."""
    text = f"{value:.{digits}f}"
    if float(text) == 1.0 and value < 1.0:
        text = f"{math.floor(value * 10**digits) / 10**digits:.{digits}f}"
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def pct(value: float) -> str:
    """Format a fraction as a whole-number percentage."""
    return f"{100.0 * value:.0f}%"


def _count(n: int) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    return words.get(n, str(n))


def _higher(a: float, b: float) -> str:
    return "higher" if a > b else "lower" if a < b else "equal"


def table(header: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _baseline(kn: dict[str, Any]) -> str:
    b = kn["baseline"]
    proto = kn["protocol"]
    ci = {name: b[f"{name}_ci95"] for name in ("auc_var", "auc_ar1", "tpr_ar1")}
    rows = [
        [
            "variance",
            f"{num(b['auc_var'], 4)} ({num(ci['auc_var'][0], 4)} to {num(ci['auc_var'][1], 4)})",
            num(b["tpr_var"]),
            num(b["median_tau_ramp_var"]),
            num(b["median_tau_null_var"]),
        ],
        [
            "AR(1)",
            f"{num(b['auc_ar1'], 4)} ({num(ci['auc_ar1'][0], 4)} to {num(ci['auc_ar1'][1], 4)})",
            f"{num(b['tpr_ar1'])} ({num(ci['tpr_ar1'][0])} to {num(ci['tpr_ar1'][1])})",
            num(b["median_tau_ramp_ar1"]),
            num(b["median_tau_null_ar1"]),
        ],
    ]
    intro = (
        f"**Baseline** (sigma = {b['sigma']:g}, ramp of {b['duration']:g} time units, "
        f"{b['n_runs']} ramp and {b['n_runs']} control runs, seed {b['seed']}; rolling window "
        f"{proto['window_time']:g} time units, analysis stops at {pct(proto['analysis_fraction'])} "
        "of the ramp). Intervals are 95% percentile bootstrap intervals that resample the runs "
        "of this single simulation; they do not include the variation between seeds."
    )
    header = [
        "Indicator",
        "AUC (95% CI)",
        "TPR at 5% FPR",
        "Median tau, ramp",
        "Median tau, control",
    ]
    return intro + "\n\n" + table(header, rows)


def _horizon(kn: dict[str, Any]) -> str:
    h = kn["horizon"]
    proto = kn["protocol"]
    rows = [
        [
            pct(r["analysis_fraction"]),
            f"{r['t_end']:g}",
            f"{r['time_before_fold']:g}",
            num(r["auc_var"], 3),
            num(r["auc_ar1"], 3),
        ]
        for r in h["rows"]
    ]
    text = (
        f"**Analysis horizon.** It was fixed in advance at {pct(proto['analysis_fraction'])} of "
        f"the ramp, just before the fold, which the ramp reaches at t = {h['fold_time']:g} "
        f"({pct(h['fold_fraction_of_ramp'])} of the ramp). An analyst who knows where the fold is "
        "can pick such a horizon; with real data the fold position is unknown. The metrics "
        "depend strongly on that choice (baseline run, seed "
        f"{h['seed']}):"
    )
    header = ["Analysis stops at", "t", "Time before the fold", "AUC variance", "AUC AR(1)"]
    return text + "\n\n" + table(header, rows)


def _tipping(kn: dict[str, Any]) -> str:
    t = kn["tipping_vs_fold"]
    b = t["baseline"]
    clear = [r for r in t["by_sigma"] if r["frac_tip_before_fold"] >= 0.999]
    parts = [
        f"**Tipping happens near the fold, and noise pulls it forward.** At baseline noise "
        f"(sigma = {b['sigma']:g}) the median ramp run tips {b['median_advance_before_fold']:.0f} "
        f"time units before the fold (t = {t['fold_time']:g}) and {pct(b['frac_tip_before_fold'])} "
        f"of the runs tip before it; the deterministic system would tip "
        f"{t['deterministic_delay_after_fold']:g} time units after the fold."
    ]
    if clear:
        first = clear[0]
        last = clear[-1]
        parts.append(
            f"From sigma = {first['sigma']:g} on, every ramp run tips by noise before the fold "
            f"(median r at the tip {num(first['median_r_at_tip'], 3)} at sigma = "
            f"{first['sigma']:g} and {num(last['median_r_at_tip'], 3)} at sigma = "
            f"{last['sigma']:g}, against r = {-kn['model']['fold_r']:.3f} at the fold)."
        )
    return " ".join(parts)


def _sweep_tables(summary: pd.DataFrame) -> str:
    seeds = _count(int(summary["n_seeds"].min()))
    sigmas = sorted(summary["sigma"].unique())
    durations = sorted(summary["duration"].unique())
    windows = {d: int(summary.loc[summary["duration"] == d, "window"].iloc[0]) for d in durations}
    header = ["sigma \\ ramp duration (window, samples)"] + [
        f"{d:g} ({windows[d]})" for d in durations
    ]

    def grid(column: str, digits: int, fmt: Any = num) -> str:
        rows = []
        for s in sigmas:
            row = [f"{s:g}"]
            for d in durations:
                cell = summary[(summary["sigma"] == s) & (summary["duration"] == d)].iloc[0]
                row.append(fmt(float(cell[column]), digits))
            rows.append(row)
        return table(header, rows)

    def share(value: float, _digits: int) -> str:
        return pct(value)

    return "\n\n".join(
        [
            f"*AUC of the variance (mean over {seeds} seeds):*\n\n" + grid("auc_var_mean", 3),
            f"*AUC of AR(1) (mean over {seeds} seeds):*\n\n" + grid("auc_ar1_mean", 3),
            "*Share of ramp runs that tipped before the analysis horizon (noise-induced, "
            "before enough signal has built up):*\n\n" + grid("frac_ramp_tipped_early", 0, share),
        ]
    )


def _sweep_reading(kn: dict[str, Any], summary: pd.DataFrame) -> str:
    n_cells = len(summary)
    var_ahead = int((summary["auc_var_mean"] >= summary["auc_ar1_mean"]).sum())
    ar1_ahead = summary[summary["auc_ar1_mean"] > summary["auc_var_mean"]]
    paired = kn["sweep_paired"]
    wins = paired["auc_variance_wins"]
    spread = max(
        float((summary[f"{m}_ci_hi"] - summary[f"{m}_ci_lo"]).max()) for m in ("auc_var", "auc_ar1")
    )
    exceptions = ", ".join(f"({e['sigma']:g}, {e['duration']:g})" for e in paired["auc_exceptions"])
    text = (
        f"Variance matches or beats AR(1) almost everywhere: its seed-mean AUC is at least that "
        f"of AR(1) in {var_ahead} of {n_cells} cells"
    )
    if len(ar1_ahead):
        cells = ", ".join(f"({r.sigma:g}, {r.duration:g})" for r in ar1_ahead.itertuples())
        text += f" (AR(1) is ahead at (sigma, duration) = {cells})"
    text += (
        f". Paired by seed, the variance AUC is higher than the AR(1) AUC in all "
        f"{paired['n_seeds']} seeds in {wins['all_seeds']} of {paired['n_cells']} cells, in some "
        f"seeds in {wins['some_seeds']} cells (at (sigma, duration) = {exceptions}) and in no "
        f"seed in {wins['no_seed']}. With constant noise the variance is therefore at least as "
        "good as AR(1); the advantage of AR(1) appears when the noise amplitude changes (below)."
    )
    text += (
        "\n\n"
        "The rolling window is tied to the ramp duration in this sweep (10% of the duration, "
        "see the window sizes in the column headers), so duration and window length are not "
        "separated here. "
    )
    text += _window_vs_duration(kn)
    seeds = _count(int(summary["n_seeds"].min()))
    text += (
        "\n\n"
        f"*Seed variation.* The sweep has {seeds} seeds per cell. `auc_*_ci_lo` and "
        f"`auc_*_ci_hi` in `results/sweep_summary.parquet` are percentile bootstrap limits of a "
        f"mean of {seeds} values, which is effectively the range over the {seeds} seeds, not a "
        "confidence interval "
        f"(the widest range in the AUC columns is {num(spread, 2)})."
    )
    return text


def _window_vs_duration(kn: dict[str, Any]) -> str:
    w = kn["window_vs_duration"]
    rows = {(r["duration"], r["window_samples"], r["detrend_samples"]): r for r in w["rows"]}
    same_long = rows[(2000.0, 20, 5)]
    same_short = rows[(100.0, 20, 5)]
    longer_short = rows[(100.0, 60, 15)]
    return (
        f"Separate checks (sigma = {w['sigma']:g}, one seed) show that both matter: with the "
        f"same {same_long['window_time']:g}-unit window the variance AUC is "
        f"{num(same_long['auc_var'], 3)} on the {same_long['duration']:g}-unit ramp and "
        f"{num(same_short['auc_var'], 3)} on the {same_short['duration']:g}-unit ramp (the ramp "
        f"duration acts on its own), and on the short ramp a window of "
        f"{longer_short['window_time']:g} units gives {num(longer_short['auc_var'], 3)}, "
        f"{_higher(longer_short['auc_var'], same_short['auc_var'])} than "
        f"{num(same_short['auc_var'], 3)} (the window acts on its own)."
    )


def _confound(conf: dict[str, Any]) -> str:
    cfg = conf["config"]
    sc = conf["scenarios"]
    labels = {
        "fold": "Fold approach, constant noise (positive control)",
        "noise_0.10": "Noise rising to 0.10, r = 0 (false-alarm test)",
        "noise_0.15": "Noise rising to 0.15, r = 0 (false-alarm test)",
        "mixed_vs_noise_0.10": "Fold approach and noise rising to 0.10, against noise rising alone",
        "mixed_vs_noise_0.15": "Fold approach and noise rising to 0.15, against noise rising alone",
    }
    rows = []
    for key, label in labels.items():
        if key not in sc:
            continue
        p = sc[key]["pooled"]
        rows.append(
            [
                label,
                f"{num(p['variance']['auc'], 4)} ({num(p['variance']['auc_ci95'][0], 4)} to "
                f"{num(p['variance']['auc_ci95'][1], 4)})",
                f"{num(p['ar1']['auc'], 4)} ({num(p['ar1']['auc_ci95'][0], 4)} to "
                f"{num(p['ar1']['auc_ci95'][1], 4)})",
                num(p["variance"]["tpr_at_5pct_fpr"]),
                num(p["ar1"]["tpr_at_5pct_fpr"]),
            ]
        )
    header = [
        "Scenario",
        "AUC variance (95% CI)",
        "AUC AR(1) (95% CI)",
        "TPR variance",
        "TPR AR(1)",
    ]
    noise = sc["noise_0.15"]["pooled"]
    noise_sigma = sc["noise_0.15"]["sigma_end"]
    both = sc["mixed_vs_noise_0.15"]["pooled"]
    text = (
        "**Where AR(1) helps: a changing noise amplitude.** The variance scales with sigma squared "
        "and the AR(1) does not, so when the noise grows while the system stays far from the "
        "fold the variance gives a false alarm and AR(1) does not. Pooled over "
        f"{len(cfg['seeds'])} seeds ({cfg['n_runs_per_group']} runs per group and seed, "
        "bootstrap intervals resample runs), with sigma rising from "
        f"{cfg['sigma_start']:g} to {noise_sigma:g} at constant r = 0, the variance flags "
        f"{pct(noise['variance']['tpr_at_5pct_fpr'])} of the runs at the 5% false-positive "
        f"threshold (AUC {num(noise['variance']['auc'], 4)}) while AR(1) flags "
        f"{pct(noise['ar1']['tpr_at_5pct_fpr'])} (AUC {num(noise['ar1']['auc'], 4)}, close to "
        "chance). When the fold approach has to be recognised against a background of rising "
        f"noise, the AUC of the variance is {num(both['variance']['auc'], 4)} and that of AR(1) "
        f"is {num(both['ar1']['auc'], 4)}."
    )
    return text + "\n\n" + table(header, rows)


def _closing(kn: dict[str, Any]) -> str:
    surv = [r for r in kn["survivors"]["rows"] if r["frac_null_tipped"] > 0]
    worst = max(surv, key=lambda r: r["frac_null_tipped"]) if surv else None
    text = (
        "**Reading the numbers.** The AUC is computed on the runs that survive long enough to "
        "be analysed, so read it together with the tipped shares above."
    )
    if worst is not None:
        text += (
            f" At sigma = {worst['sigma']:g} and a ramp of {worst['duration']:g} the control "
            f"group itself tips in {pct(worst['frac_null_tipped'])} of the runs and only "
            f"{worst['n_valid_ramp']:.0f} of the ramp runs remain valid on average."
        )
    return text


def render(kn: dict[str, Any], summary: pd.DataFrame, conf: dict[str, Any]) -> str:
    """Build the Markdown that goes between the RESULTS markers."""
    n_runs = load_sweep_config(default_sweep_config_path()).n_runs
    parts = [
        "All numbers below are generated by `scripts/fill_readme.py` from `results/` "
        "(`key_numbers.json`, `sweep_summary.parquet`, `confound.json`).",
        _baseline(kn),
        _horizon(kn),
        _tipping(kn),
        f"**Noise by ramp duration** ({n_runs} runs per group and cell, "
        f"{_count(int(summary['n_seeds'].min()))} seeds per cell). "
        "AUC of Kendall's tau, ramp against control:\n\n" + _sweep_tables(summary),
        _sweep_reading(kn, summary),
        _confound(conf),
        _closing(kn),
    ]
    return "\n\n".join(parts)


def replace_block(readme: str, block: str) -> str:
    """Return ``readme`` with the text between the markers replaced by ``block``."""
    start, end = readme.index(START), readme.index(END)
    return readme[: start + len(START)] + "\n" + block + "\n" + readme[end:]


def main(argv: list[str] | None = None) -> int:
    """Rewrite (or, with ``--check``, verify) the RESULTS block of the README."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="only report whether it is current")
    parser.add_argument("--readme", type=Path, default=project_root() / "README.md")
    args = parser.parse_args(argv)

    results = results_dir()
    kn = json.loads((results / "key_numbers.json").read_text(encoding="utf-8"))
    conf = json.loads((results / "confound.json").read_text(encoding="utf-8"))
    summary = pd.read_parquet(results / "sweep_summary.parquet")
    current = args.readme.read_text(encoding="utf-8")
    updated = replace_block(current, render(kn, summary, conf))
    if args.check:
        if updated != current:
            print("README.md RESULTS block is out of date; run scripts/fill_readme.py")
            return 1
        return 0
    args.readme.write_text(updated, encoding="utf-8")
    print(f"updated {args.readme}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
