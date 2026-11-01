# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Static figures and animations with Spanish and English labels (`--lang es|en`).
- Command-line interface `tipping` with `simulate`, `sweep`, `figures`, `animate` and `reproduce`.
- Documentation: README, mathematical derivations (`docs/math.md`), design decisions
  (`docs/design.md`) and a Windows setup guide (`docs/windows-setup.md`).
- Tooling: `uv` project, `just` task runner, pre-commit hooks and a GitHub Actions workflow on
  Linux and Windows.
