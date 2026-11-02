# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tipping confound`, `tipping key-numbers` and `tipping deck` commands; `tipping reproduce` now also
  runs the confound experiment and the key numbers, so the deck can be built from a clean checkout.
- `scripts/fill_readme.py` fills the README results block from `results/`.
- `evaluate.analysis_horizon` and `evaluate.analysis_stop` (one definition of where a run's analysis
  ends) and `evaluate.run_taus_with_indicators`.
- CI job that smoke-tests the deck helpers.

### Changed

- Pre-commit runs ruff and mypy from the locked environment instead of a pinned ruff mirror.
- CI syncs with `--locked`, has timeouts and cancels superseded runs on pull requests only.
- `sweep.run_sweep` takes a `log` callable instead of importing `typer`.
- `confound.FOLD_R_END` is now `RAMP_R_END` (the old name stays as an alias); the confound ramp
  starts at `sim.r_start` and its fold group follows `sim.r_end`.
- `theory.ou_*` take their growth-rate argument as `rate`.
- The `*_ci_lo` / `*_ci_hi` columns of the sweep summary are documented as a range over seeds, not a
  confidence interval.

### Fixed

- Type-check on Python 3.11 (`float()` around the naive rolling variance in a test).
- Parquet files written by `write_parquet` get the umask default mode instead of 0600.
- `bootstrap_ci` and `bootstrap_mean_ci` reject `n_boot < 1` with a clear error.

## [0.1.0] - 2026-11-01

### Added

- Closed-form model of the bistable system `dx = (r + x - x^3) dt + sigma dW`: drift, potential,
  growth rate, equilibria (trigonometric form and Cardano) and stability classification.
- Linear Ornstein-Uhlenbeck theory for the stationary variance, the autocorrelation function and the
  sampled AR(1) coefficient.
- Vectorised Euler-Maruyama simulator with linear parameter ramps and a constant-parameter control.
- Early-warning indicators (detrending, rolling variance, rolling lag-1 autocorrelation, Kendall tau)
  and evaluation metrics (AUC, TPR at 5% false-positive rate, bootstrap confidence intervals).
- Parameter sweep over noise level, ramp duration and seed, stored as Parquet and queryable with DuckDB.
- Noise-amplitude confound experiment (`confound.py`, `simulate(..., sigma_end=...)`) and the
  `key_numbers.py` module that computes every number quoted in the talk.
- Spanish slide deck builder and speaker-notes exporter in `deck/`, and the extra confound figure
  (`viz/figures_extra.py`).
- Static figures and animations with Spanish and English labels (`--lang es|en`).
- Command-line interface `tipping` with `simulate`, `sweep`, `figures`, `animate` and `reproduce`.
- Documentation: README, mathematical derivations (`docs/math.md`), design decisions
  (`docs/design.md`) and a Windows setup guide (`docs/windows-setup.md`).
- Tooling: `uv` project, `just` task runner, pre-commit hooks and a GitHub Actions workflow on
  Linux and Windows.
