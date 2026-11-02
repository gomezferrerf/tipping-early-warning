"""Command-line interface.

``tipping simulate | sweep | confound | key-numbers | figures | animate | deck | reproduce``.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import typer

from tipping.config import ExperimentConfig, load_config
from tipping.evaluate import Experiment, run_experiment
from tipping.paths import default_config_path, project_root
from tipping.simulate import first_crossing

app = typer.Typer(
    name="tipping",
    help="Early-warning signals near a saddle-node bifurcation: simulate, sweep, plot, animate.",
    no_args_is_help=True,
    add_completion=False,
)


class Language(StrEnum):
    """Language of figure and animation labels."""

    es = "es"
    en = "en"


def _load_entry(module: str, attribute: str, command: str) -> Callable[..., Any]:
    """Import ``module.attribute`` lazily, exiting with a friendly message if it is missing."""
    try:
        entry: Callable[..., Any] = getattr(importlib.import_module(module), attribute)
    except ModuleNotFoundError as error:
        if error.name != module:
            raise
        typer.echo(
            f"The '{command}' command needs the module '{module}', which is not available yet "
            "in this checkout. Nothing was done.",
            err=True,
        )
        raise typer.Exit(code=1) from error
    return entry


def _fmt(value: float, digits: int = 3) -> str:
    return "n/a" if not np.isfinite(value) else f"{value:.{digits}f}"


def _median(values: Any) -> float:
    return float(np.median(values)) if len(values) else float("nan")


def format_summary(cfg: ExperimentConfig, experiment: Experiment, seed: int, elapsed: float) -> str:
    """Render the compact text summary printed by ``tipping simulate``.

    Parameters
    ----------
    cfg : ExperimentConfig
        Configuration that produced the experiment.
    experiment : Experiment
        Simulated trajectories and their evaluation.
    seed : int
        Master seed used.
    elapsed : float
        Wall-clock time in seconds.

    Returns
    -------
    str
        Multi-line summary table.
    """
    sim, res = cfg.sim, experiment.result
    n = sim.n_runs
    fold_time = sim.fold_time()
    fold = (
        "fold not reached by the ramp"
        if fold_time is None
        else f"fold reached at t = {fold_time:.0f}"
    )

    tips = first_crossing(experiment.ramp.x, cfg.indicators.tip_threshold)
    tipped = tips < experiment.ramp.n_samples
    median_tip = float(np.median(experiment.ramp.t[tips[tipped]])) if tipped.any() else float("nan")

    tpr_label = f"TPR @ {cfg.indicators.fpr:.0%} FPR"
    lines = [
        f"Baseline experiment (seed {seed}): r {sim.r_start:g} -> {sim.r_end:g} over "
        f"t = {sim.duration:g}, sigma = {sim.sigma:g}, {n} ramp + {n} control runs",
        f"{fold}; median tip time of tipped ramp runs: {_fmt(median_tip, 0)} "
        f"({int(tipped.sum())}/{n} tipped by the end)",
        "",
        f"{'':<26}{'variance':>10}{'AR(1)':>10}",
        f"{'AUC':<26}{_fmt(res.auc_var):>10}{_fmt(res.auc_ar1):>10}",
        f"{tpr_label:<26}{_fmt(res.tpr_var):>10}{_fmt(res.tpr_ar1):>10}",
        f"{'median tau, ramp':<26}{_fmt(_median(res.tau_ramp_var)):>10}"
        f"{_fmt(_median(res.tau_ramp_ar1)):>10}",
        f"{'median tau, control':<26}{_fmt(_median(res.tau_null_var)):>10}"
        f"{_fmt(_median(res.tau_null_ar1)):>10}",
        "",
        f"ramp runs tipped before analysis end: {round(res.frac_ramp_tipped_early * n)}/{n}"
        f" ({res.frac_ramp_tipped_early:.1%})",
        f"control runs tipped at any time:      {round(res.frac_null_tipped * n)}/{n}"
        f" ({res.frac_null_tipped:.1%})",
        f"valid runs (ramp / control):          {res.n_valid_ramp} / {res.n_valid_null}",
        f"elapsed: {elapsed:.1f} s",
    ]
    return "\n".join(lines)


@app.command()
def simulate(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="YAML file (default: configs/default.yaml)."),
    ] = None,
    seed: Annotated[
        int | None, typer.Option("--seed", "-s", help="Master seed (default: from the config).")
    ] = None,
    n_runs: Annotated[int | None, typer.Option(help="Override the runs per group.")] = None,
    duration: Annotated[float | None, typer.Option(help="Override the ramp duration.")] = None,
    sigma: Annotated[float | None, typer.Option(help="Override the noise amplitude.")] = None,
) -> None:
    """Run the baseline ramp-versus-control experiment and print a summary table."""
    cfg = load_config(config if config is not None else default_config_path())
    overrides: dict[str, Any] = {
        key: value
        for key, value in (("n_runs", n_runs), ("duration", duration), ("sigma", sigma))
        if value is not None
    }
    if overrides:
        cfg = cfg.model_copy(update={"sim": cfg.sim.model_copy(update=overrides)})
    used_seed = cfg.sim.seed if seed is None else seed
    start = time.perf_counter()
    experiment = run_experiment(cfg.sim, cfg.indicators, used_seed)
    typer.echo(format_summary(cfg, experiment, used_seed, time.perf_counter() - start))


def _do_sweep(config: Path | None, out_dir: Path | None) -> None:
    run_sweep = _load_entry("tipping.sweep", "run_sweep", "sweep")
    path = run_sweep(config, out_dir, log=typer.echo)
    typer.echo(f"Sweep written to {path}")


def _do_confound() -> None:
    main = _load_entry("tipping.confound", "main", "confound")
    parquet_path, json_path = main()
    typer.echo(f"Confound experiment written to {parquet_path} and {json_path}")


def _do_key_numbers() -> None:
    main = _load_entry("tipping.key_numbers", "main", "key-numbers")
    main()


def _do_figures(lang: Language, out_dir: Path | None, sweep_path: Path | None) -> None:
    make_all = _load_entry("tipping.viz.figures", "make_all", "figures")
    for path in make_all(lang.value, out_dir, sweep_path):
        typer.echo(f"Wrote {path}")


def _do_animate(lang: Language, out_dir: Path | None, fps: int) -> None:
    make_all = _load_entry("tipping.viz.animations", "make_all", "animate")
    for path in make_all(lang.value, out_dir, fps):
        typer.echo(f"Wrote {path}")


@app.command()
def sweep(
    config: Annotated[Path | None, typer.Option("--config", "-c", help="Sweep YAML file.")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Output directory for the tables.")] = None,
) -> None:
    """Run the noise-by-duration parameter sweep and write the result tables."""
    _do_sweep(config, out_dir)


@app.command()
def confound() -> None:
    """Run the noise-amplitude confound experiment and write results/confound.*."""
    _do_confound()


@app.command("key-numbers")
def key_numbers() -> None:
    """Compute every number quoted in the talk and write results/key_numbers.json."""
    _do_key_numbers()


@app.command()
def figures(
    lang: Annotated[Language, typer.Option(help="Label language.")] = Language.en,
    out_dir: Annotated[Path | None, typer.Option(help="Output directory for the PNGs.")] = None,
    sweep_path: Annotated[
        Path | None, typer.Option(help="Sweep table (default: results/sweep.parquet).")
    ] = None,
) -> None:
    """Render all static figures."""
    _do_figures(lang, out_dir, sweep_path)


@app.command()
def animate(
    lang: Annotated[Language, typer.Option(help="Label language.")] = Language.en,
    out_dir: Annotated[Path | None, typer.Option(help="Output directory for the MP4s.")] = None,
    fps: Annotated[int, typer.Option(help="Frames per second.")] = 30,
) -> None:
    """Render all animations."""
    _do_animate(lang, out_dir, fps)


@app.command()
def deck(
    repo_url: Annotated[
        str | None, typer.Option(help="Repository URL shown on the last slide.")
    ] = None,
) -> None:
    """Build the slide deck into deck/build/ (needs the deck extra and the results/ files)."""
    script = project_root() / "deck" / "build_deck.py"
    if not script.is_file():
        typer.echo(
            f"The deck script {script} was not found; run this from a source checkout.", err=True
        )
        raise typer.Exit(code=1)
    if importlib.util.find_spec("pptx") is None:
        typer.echo(
            "The 'deck' command needs python-pptx. Install it with: uv sync --extra deck",
            err=True,
        )
        raise typer.Exit(code=1)
    command = [sys.executable, str(script)]
    if repo_url is not None:
        command += ["--repo-url", repo_url]
    completed = subprocess.run(command, cwd=project_root(), check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


@app.command()
def reproduce() -> None:
    """Regenerate everything: sweep, confound, key numbers, figures (es, en), animations (es)."""
    _do_sweep(None, None)
    _do_confound()
    _do_key_numbers()
    _do_figures(Language.es, None, None)
    _do_figures(Language.en, None, None)
    _do_animate(Language.es, None, 30)


if __name__ == "__main__":
    app()
