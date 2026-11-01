"""Typed configuration (pydantic v2) and YAML loading.

The models are frozen and reject unknown keys, so a typo in a YAML file fails loudly instead
of silently falling back to a default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tipping.model import FOLD_R
from tipping.simulate import Ramp


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SimConfig(_Frozen):
    """Parameters of one ramp-versus-control simulation experiment.

    Attributes
    ----------
    dt : float
        Integration step.
    sample_every : int
        Integration steps per stored sample (sampling interval ``dt * sample_every``).
    sigma : float
        Noise amplitude.
    x0 : float
        Initial state (the upper branch at ``r_start = 0`` is ``x = 1``).
    r_start, r_end : float
        Ends of the linear ramp; the control group keeps ``r = r_start``.
    duration : float
        Ramp length in time units.
    n_runs : int
        Runs per group (ramp and control).
    seed : int
        Master seed from which the ramp and control seeds are derived.
    """

    dt: float = Field(default=0.01, gt=0.0)
    sample_every: int = Field(default=50, ge=1)
    sigma: float = Field(default=0.05, ge=0.0)
    x0: float = 1.0
    r_start: float = 0.0
    r_end: float = -0.6
    duration: float = Field(default=2000.0, gt=0.0)
    n_runs: int = Field(default=300, ge=1)
    seed: int = Field(default=42, ge=0)

    @model_validator(mode="after")
    def _duration_covers_a_sample(self) -> SimConfig:
        if self.duration < self.dt * self.sample_every:
            msg = "duration must be at least one sampling interval (dt * sample_every)"
            raise ValueError(msg)
        return self

    @property
    def sample_interval(self) -> float:
        """Time between stored samples."""
        return self.dt * self.sample_every

    def ramp(self) -> Ramp:
        """Return the control-parameter ramp ``r_start -> r_end`` over ``duration``."""
        return Ramp(self.r_start, self.r_end, self.duration)

    def control(self) -> Ramp:
        """Return the constant schedule ``r = r_start`` used for the control group."""
        return Ramp.constant(self.r_start, self.duration)

    def fold_time(self) -> float | None:
        """Time at which the ramp reaches the fold ``r = -FOLD_R`` that ends the upper branch.

        Returns
        -------
        float or None
            The crossing time, or ``None`` if the ramp never reaches ``r = -FOLD_R``.
        """
        if self.r_end < -FOLD_R <= self.r_start:
            return self.duration * (self.r_start + FOLD_R) / (self.r_start - self.r_end)
        return None


class IndicatorConfig(_Frozen):
    """Parameters of indicator computation and evaluation.

    Attributes
    ----------
    window : int
        Rolling-window length in samples.
    detrend_window : int
        Moving-average length in samples used to detrend (also the safety margin before a tip).
    analysis_fraction : float
        Fraction of each trajectory analysed at most.
    min_points : int
        Minimum number of subsampled indicator values for a run to be valid.
    tau_step : int or None
        Subsampling step for Kendall's tau; ``None`` means ``max(window // 40, 1)``.
    tip_threshold : float
        A run has tipped at the first sample with ``x < tip_threshold``.
    fpr : float
        False-positive rate at which the true-positive rate is reported.
    """

    window: int = Field(default=400, ge=3)
    detrend_window: int = Field(default=100, ge=1)
    analysis_fraction: float = Field(default=0.6, gt=0.0, le=1.0)
    min_points: int = Field(default=15, ge=2)
    tau_step: int | None = Field(default=None, ge=1)
    tip_threshold: float = 0.0
    fpr: float = Field(default=0.05, gt=0.0, lt=1.0)

    def resolved_step(self) -> int:
        """Return the subsampling step for Kendall's tau."""
        return self.tau_step if self.tau_step is not None else max(self.window // 40, 1)

    @classmethod
    def for_sweep(
        cls,
        duration: float,
        sample_interval: float,
        window_fraction: float = 0.10,
        min_window: int = 10,
        **overrides: Any,
    ) -> IndicatorConfig:
        """Build the window rule used for parameter sweeps.

        ``window = max(min_window, round(window_fraction * duration / sample_interval))`` and
        ``detrend_window = max(5, window // 4)``.

        Parameters
        ----------
        duration : float
            Ramp length in time units.
        sample_interval : float
            Time between stored samples.
        window_fraction : float, default 0.10
            Rolling window as a fraction of the ramp.
        min_window : int, default 10
            Lower bound of the window in samples.
        **overrides
            Any other field of this model, overriding its default.

        Returns
        -------
        IndicatorConfig
            Configuration with the derived windows.
        """
        window = max(min_window, round(window_fraction * duration / sample_interval))
        return cls(window=window, detrend_window=max(5, window // 4), **overrides)


class ExperimentConfig(_Frozen):
    """A full ramp-versus-control experiment: simulation plus indicator settings."""

    sim: SimConfig = Field(default_factory=lambda: SimConfig())
    indicators: IndicatorConfig = Field(default_factory=lambda: IndicatorConfig())


class SweepConfig(_Frozen):
    """Grid of experiments over noise level and ramp duration, repeated over seeds.

    Attributes
    ----------
    sigmas, durations : list of float
        Grid axes (noise amplitude and ramp length in time units).
    n_runs : int
        Runs per group and grid cell.
    seeds : list of int
        Master seeds; each (sigma, duration, seed) is one independent experiment.
    dt, sample_every, x0, r_start, r_end
        As in :class:`SimConfig`.
    window_fraction, min_window
        Window rule, see :meth:`IndicatorConfig.for_sweep`.
    analysis_fraction, min_points, tip_threshold, fpr
        As in :class:`IndicatorConfig`.
    n_boot : int
        Bootstrap resamples for confidence intervals.
    n_jobs : int
        Worker processes (``-1`` for all cores, ``1`` for serial).
    """

    sigmas: list[float] = Field(default_factory=lambda: [0.03, 0.05, 0.10, 0.15, 0.30])
    durations: list[float] = Field(default_factory=lambda: [100.0, 200.0, 400.0, 1000.0, 2000.0])
    n_runs: int = Field(default=300, ge=1)
    seeds: list[int] = Field(default_factory=lambda: [1, 2, 3])
    dt: float = Field(default=0.01, gt=0.0)
    sample_every: int = Field(default=50, ge=1)
    x0: float = 1.0
    r_start: float = 0.0
    r_end: float = -0.6
    window_fraction: float = Field(default=0.10, gt=0.0, le=1.0)
    min_window: int = Field(default=10, ge=3)
    analysis_fraction: float = Field(default=0.6, gt=0.0, le=1.0)
    min_points: int = Field(default=15, ge=2)
    tip_threshold: float = 0.0
    fpr: float = Field(default=0.05, gt=0.0, lt=1.0)
    n_boot: int = Field(default=1000, ge=1)
    n_jobs: int = -1

    def sim_config(self, sigma: float, duration: float, seed: int) -> SimConfig:
        """Return the simulation config of one grid cell."""
        return SimConfig(
            dt=self.dt,
            sample_every=self.sample_every,
            sigma=sigma,
            x0=self.x0,
            r_start=self.r_start,
            r_end=self.r_end,
            duration=duration,
            n_runs=self.n_runs,
            seed=seed,
        )

    def indicator_config(self, duration: float) -> IndicatorConfig:
        """Return the indicator config of a grid cell using the sweep window rule."""
        return IndicatorConfig.for_sweep(
            duration,
            self.dt * self.sample_every,
            window_fraction=self.window_fraction,
            min_window=self.min_window,
            analysis_fraction=self.analysis_fraction,
            min_points=self.min_points,
            tip_threshold=self.tip_threshold,
            fpr=self.fpr,
        )


def _read_mapping(path: Path | str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"{path}: expected a YAML mapping at the top level"
        raise ValueError(msg)
    return data


def load_config(path: Path | str) -> ExperimentConfig:
    """Load an experiment configuration from a YAML file.

    Parameters
    ----------
    path : pathlib.Path or str
        YAML file with optional ``sim`` and ``indicators`` sections.

    Returns
    -------
    ExperimentConfig
        Validated configuration; missing fields take the baseline defaults.

    Raises
    ------
    pydantic.ValidationError
        If a value is invalid or a key is unknown.
    """
    return ExperimentConfig.model_validate(_read_mapping(path))


def load_sweep_config(path: Path | str) -> SweepConfig:
    """Load a sweep configuration from a YAML file.

    Parameters
    ----------
    path : pathlib.Path or str
        YAML file whose fields are either at the top level or nested under a ``sweep`` key.

    Returns
    -------
    SweepConfig
        Validated configuration; missing fields take the defaults of the brief.
    """
    data = _read_mapping(path)
    nested = data.get("sweep")
    return SweepConfig.model_validate(nested if isinstance(nested, dict) else data)
