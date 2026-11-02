# Contributor guide

## Purpose

Simulation study of early-warning signals (rolling variance and lag-1 autocorrelation) near the saddle-node bifurcation of `dx = (r + x - x^3) dt + sigma dW`, evaluated against a control group and a sweep over noise level and ramp duration. The model has a known ground truth, so physics oracles can be used in tests. Background: `README.md`, `docs/math.md`, `docs/design.md`.

## Commands

Use `uv`; `just` recipes are shortcuts for the same lines. Must work in PowerShell: no `make`, no bash-only syntax, no `/tmp`.

| Task | Command |
| --- | --- |
| Setup | `uv sync --locked --group dev --extra deck` |
| Test | `uv run pytest` (all) or `uv run pytest -m "not slow"` (fast set; `slow` marks the long statistical tests) |
| Lint / format | `uv run ruff check` / `uv run ruff format` |
| Typecheck | `uv run mypy` (strict, covers `src` and `tests`) |
| All checks | `just check` |
| Baseline run | `uv run tipping simulate` |
| Confound experiment | `uv run tipping confound` (writes `results/confound.*`) |
| Key numbers | `uv run tipping key-numbers` (writes `results/key_numbers.json`; needs the sweep) |
| Slide deck | `uv run tipping deck [--repo-url URL]` or `just deck` (needs the `deck` extra) |
| README results block | `uv run python scripts/fill_readme.py` (`--check` to verify) |
| Reproduce everything | `uv run tipping reproduce` (sweep, confound, key numbers, figures es and en, animations es) |

Before declaring work done, run ruff check, ruff format --check, mypy and pytest. Before pushing, also run `UV_PYTHON=3.11 uv run mypy` (PowerShell: `$env:UV_PYTHON="3.11"; uv run mypy`): CI tests Python 3.11, which resolves older NumPy stubs than 3.13 and can reject code that 3.13 accepts.

## Architecture (`src/tipping`)

| Module | Role |
| --- | --- |
| `model.py` | `FOLD_R`, `FOLD_X`, drift, potential, growth rate, closed-form `equilibria`, `classify_equilibria`, `upper_branch`, `lower_branch` |
| `theory.py` | Ornstein–Uhlenbeck variance, ACF, AR(1), `predicted_indicators` |
| `simulate.py` | `Ramp`, `simulate` (Euler–Maruyama, vectorised over runs), `first_crossing` |
| `indicators.py` | `detrend`, `rolling_variance`, `rolling_ar1`, `kendall_tau_per_run`, `compute_indicators` |
| `evaluate.py` | `auc`, `tpr_at_fpr`, `bootstrap_ci`, `analysis_stop` (the one definition of where a run's analysis ends), `run_taus`, `evaluate_pair` |
| `confound.py` | Noise-amplitude confound experiment (`sigma_end` ramps, scenarios, `results/confound.*`) |
| `key_numbers.py` | Every number quoted in the talk, written to `results/key_numbers.json` |
| `config.py` | pydantic models and `load_config`; YAML lives in `configs/` |
| `paths.py` | `project_root`, `results_dir`, `assets_dir`, `data_dir`; honours `TIPPING_ROOT` |
| `sweep.py`, `io.py` | sigma x duration x seed sweep; Parquet read/write (`results/sweep.parquet`) |
| `viz/style.py` | palette and matplotlib rcParams (do not change casually) |
| `viz/labels.py` | figure text per language |
| `viz/figures.py`, `viz/figures_extra.py`, `viz/animations.py` | PNG figures (`figures_extra`: the confound figure) and MP4 animations |
| `cli.py` | typer app `tipping`: `simulate`, `sweep`, `confound`, `key-numbers`, `figures`, `animate`, `deck`, `reproduce` |

Outside the package: `deck/build_deck.py` (Spanish slide deck, reads `results/key_numbers.json`), `deck/export_notes.py` (speaker notes from `deck/guion.md`) and `scripts/fill_readme.py` (README results block).

Heavy modules (matplotlib, imageio) are imported lazily inside CLI commands.

## Conventions

- English for code, comments, docstrings, docs and commit messages. Only the slide deck, the talk script and `lang="es"` figure labels are Spanish.
- Type hints everywhere, `mypy --strict` clean. NumPy-style docstrings on every public function and class.
- Pure functions, no global mutable state. Dataclasses are frozen.
- Randomness only through `numpy.random.default_rng(seed)` with explicit seeds.
- Paths only through `pathlib` and `tipping.paths`; no hard-coded absolute paths.
- Windows-safe: no POSIX-only calls, no shell pipelines in recipes.
- Line length 100; ruff rules are in `pyproject.toml`.

## Testing expectations

Tests encode physics oracles, not snapshots of whatever the code printed. Examples: roots satisfy the cubic; three real roots iff `|r| < 2/(3*sqrt(3))`; `growth_rate` vanishes at the fold; the OU variance `sigma^2/(2|lambda|)` and AR(1) `exp(lambda*dt)` match long simulations at small sigma; null AUC is about 0.5. Any number quoted in docs or slides must come from code that was run. Statistical tests use fixed seeds and tolerances justified by the sample size; mark expensive ones `@pytest.mark.slow`. The `*_ci_lo` / `*_ci_hi` columns of the sweep summary come from three seeds: call them a range over seeds, never a confidence interval.

## Do not

- Do not commit `data/`, `results/` or `deck/build/` (they are gitignored and regenerated).
- Never write `x ** (1/3)` for possibly negative floats: it returns a complex principal root. Use `np.cbrt`.
- Do not add dual axes or 3D to figures.
- One colour means one thing, everywhere, through `viz/style.py` (`stable`, `unstable`, `ramp`, `control`; pastel `*_fill` only for fills). Do not hard-code colours in figure code.
- Do not invent or hand-type results; do not weaken tests to make them pass.
- Do not use the word "collapse" in titles; use "tipping point". Use "saddle-node bifurcation" for the event and "saddle point" only for the 2D equilibrium type.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `ci:`) and carry no co-author trailers or tool mentions. Do not rewrite shared history or push unless asked.
- Do not edit `docs/assets/*.png` by hand; regenerate them.

## Regenerating outputs

- Figures: `uv run tipping figures --lang en` (README, writes `docs/assets/`) and `--lang es` (deck). `just figures` runs both.
- Animations: `uv run tipping animate --lang es` (MP4 plus poster PNG; needs no system ffmpeg, it uses `imageio-ffmpeg`).
- Sweep: `uv run tipping sweep`, then `confound`, `key-numbers` and `figures` again so everything uses the new table.
- Deck: `uv run tipping deck` (or `just deck`, which refreshes the key numbers first), output in `deck/build/`.
- Everything: `uv run tipping reproduce`.
- After a sweep, update the text between `<!-- RESULTS:START -->` and `<!-- RESULTS:END -->` in `README.md` with `uv run python scripts/fill_readme.py`; it reads only `results/`, so never type those numbers by hand.
