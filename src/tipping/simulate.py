"""Euler-Maruyama simulation of ``dx = (r(t) + x - x**3) dt + sigma dW``.

The simulation is vectorised across independent runs. Gaussian increments are drawn in blocks
(one ``(sample_every, n_runs)`` block per output sample) rather than one small call per step,
so the baseline experiment (300 runs, 200 000 steps) takes a few seconds. The noise stream is
a pure function of ``seed``: for a fixed ``dt`` and ``duration`` the trajectory is identical
whatever ``sample_every`` is, because the stream is consumed step by step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import overload

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]


@dataclass(frozen=True)
class Ramp:
    """Linear ramp of the control parameter, held constant afterwards.

    Attributes
    ----------
    r_start : float
        Value of ``r`` at ``t = 0``.
    r_end : float
        Value of ``r`` at ``t = duration``.
    duration : float
        Length of the ramp (and of the simulation) in time units.
    """

    r_start: float
    r_end: float
    duration: float

    def __post_init__(self) -> None:
        """Validate the duration."""
        if not self.duration > 0.0:
            msg = f"duration must be positive, got {self.duration!r}"
            raise ValueError(msg)

    @overload
    def r_at(self, t: float) -> float: ...
    @overload
    def r_at(self, t: FloatArray) -> FloatArray: ...
    def r_at(self, t: float | FloatArray) -> float | FloatArray:
        """Control parameter at time ``t`` (clamped to ``[r_start, r_end]``).

        Parameters
        ----------
        t : float or numpy.ndarray
            Time(s).

        Returns
        -------
        float or numpy.ndarray
            ``r_start + (r_end - r_start) * clip(t / duration, 0, 1)``.
        """
        frac = np.clip(t / self.duration, 0.0, 1.0)
        return self.r_start + (self.r_end - self.r_start) * frac

    @classmethod
    def constant(cls, r: float, duration: float) -> Ramp:
        """Build a control ramp that keeps ``r`` fixed.

        Parameters
        ----------
        r : float
            Constant control parameter.
        duration : float
            Length of the simulation.

        Returns
        -------
        Ramp
            A ramp with ``r_start == r_end == r``.
        """
        return cls(r_start=r, r_end=r, duration=duration)


@dataclass(frozen=True, eq=False)
class Trajectories:
    """Sampled trajectories of independent runs sharing one control-parameter schedule.

    Attributes
    ----------
    t : numpy.ndarray
        Sample times, shape ``(n_samples,)``; ``t[0] == 0``.
    r : numpy.ndarray
        Control parameter at the sample times, shape ``(n_samples,)`` (common to all runs).
    x : numpy.ndarray
        States, shape ``(n_samples, n_runs)``; ``x[0]`` is the initial condition.
    sigma : float
        Noise amplitude used.
    dt : float
        Integration step.
    sample_every : int
        Number of integration steps between stored samples.
    seed : int
        Seed of the random generator.
    sigma_end : float or None
        Noise amplitude at ``t = duration`` if the amplitude was ramped, else ``None``
        (constant noise ``sigma``).
    """

    t: FloatArray
    r: FloatArray
    x: FloatArray
    sigma: float
    dt: float
    sample_every: int
    seed: int
    sigma_end: float | None = None

    @property
    def n_samples(self) -> int:
        """Number of stored samples per run."""
        return int(self.x.shape[0])

    @property
    def n_runs(self) -> int:
        """Number of independent runs."""
        return int(self.x.shape[1])

    @property
    def sample_interval(self) -> float:
        """Time between stored samples (``dt * sample_every``)."""
        return self.dt * self.sample_every


def derive_seeds(seed: int) -> tuple[int, int]:
    """Derive two statistically independent seeds (ramp, control) from one master seed.

    Parameters
    ----------
    seed : int
        Master seed.

    Returns
    -------
    tuple of int
        Seeds for the ramp and the control simulation.
    """
    first, second = np.random.SeedSequence(seed).generate_state(2)
    return int(first), int(second)


def simulate(
    ramp: Ramp,
    sigma: float,
    n_runs: int,
    dt: float,
    sample_every: int,
    x0: float,
    seed: int,
    sigma_end: float | None = None,
) -> Trajectories:
    """Simulate independent runs of the stochastic bistable system.

    Uses the Euler-Maruyama scheme
    ``x_{n+1} = x_n + (r(t_n) + x_n - x_n**3) dt + sigma sqrt(dt) xi_n``, ``xi_n ~ N(0, 1)``.
    If ``sigma_end`` is given, the noise amplitude ramps linearly in time from ``sigma`` at
    ``t = 0`` to ``sigma_end`` at ``t = duration`` and the noise term of step ``n`` is
    ``sigma(t_n) sqrt(dt) xi_n``; the random stream is consumed exactly as for constant noise.
    Steps are taken until the last multiple of ``sample_every`` not exceeding
    ``round(duration / dt)``.

    Parameters
    ----------
    ramp : Ramp
        Control-parameter schedule; its ``duration`` sets the simulated time.
    sigma : float
        Noise amplitude (``>= 0``).
    n_runs : int
        Number of independent runs.
    dt : float
        Integration step.
    sample_every : int
        Store one sample every this many steps (the initial state is always stored).
    x0 : float
        Initial state of every run.
    seed : int
        Seed for ``numpy.random.default_rng``; the output is deterministic given the seed.
    sigma_end : float, optional
        Final noise amplitude (``>= 0``). ``None`` (default) keeps the noise constant at
        ``sigma``, bit-identical to the behaviour without this argument.

    Returns
    -------
    Trajectories
        Sampled states with shape ``(n_samples, n_runs)``.

    Raises
    ------
    ValueError
        If ``sigma < 0``, ``sigma_end < 0``, ``n_runs < 1``, ``dt <= 0``, ``sample_every < 1``
        or the duration is shorter than one sampling interval.
    """
    if sigma < 0.0:
        msg = f"sigma must be non-negative, got {sigma!r}"
        raise ValueError(msg)
    if sigma_end is not None and sigma_end < 0.0:
        msg = f"sigma_end must be non-negative, got {sigma_end!r}"
        raise ValueError(msg)
    if n_runs < 1 or sample_every < 1 or not dt > 0.0:
        msg = "n_runs and sample_every must be >= 1 and dt must be positive"
        raise ValueError(msg)
    n_blocks = round(ramp.duration / dt) // sample_every
    if n_blocks < 1:
        msg = "duration must cover at least one sampling interval"
        raise ValueError(msg)

    rng = np.random.default_rng(seed)
    n_steps = n_blocks * sample_every
    r_steps: list[float] = ramp.r_at(np.arange(n_steps, dtype=np.float64) * dt).tolist()
    amplitude = sigma * math.sqrt(dt)
    amplitude_steps: FloatArray | None = None
    if sigma_end is not None:
        t_steps = np.arange(n_steps, dtype=np.float64) * dt
        frac = np.clip(t_steps / ramp.duration, 0.0, 1.0)
        amplitude_steps = (sigma + (sigma_end - sigma) * frac) * math.sqrt(dt)

    x = np.full(n_runs, float(x0))
    tmp = np.empty(n_runs)
    out = np.empty((n_blocks + 1, n_runs))
    out[0] = x
    step = 0
    for block in range(n_blocks):
        noise = rng.standard_normal((sample_every, n_runs))
        if amplitude_steps is None:
            noise *= amplitude
        else:
            noise *= amplitude_steps[block * sample_every : (block + 1) * sample_every, None]
        for i in range(sample_every):
            # x += (r + x - x**3) * dt + noise[i], written with preallocated buffers.
            np.multiply(x, x, out=tmp)
            tmp *= x
            np.subtract(x, tmp, out=tmp)
            tmp += r_steps[step]
            tmp *= dt
            tmp += noise[i]
            x += tmp
            step += 1
        out[block + 1] = x

    t = np.arange(n_blocks + 1, dtype=np.float64) * (sample_every * dt)
    return Trajectories(
        t=t,
        r=ramp.r_at(t),
        x=out,
        sigma=float(sigma),
        dt=float(dt),
        sample_every=int(sample_every),
        seed=int(seed),
        sigma_end=None if sigma_end is None else float(sigma_end),
    )


def first_crossing(x: FloatArray, threshold: float = 0.0) -> IntArray:
    """Index of the first sample below ``threshold`` in each run.

    Parameters
    ----------
    x : numpy.ndarray
        States, shape ``(n_samples, n_runs)``.
    threshold : float, default 0.0
        Crossing level; a run has tipped once ``x < threshold``.

    Returns
    -------
    numpy.ndarray
        Integer array of shape ``(n_runs,)``: the first index with ``x < threshold``, or
        ``n_samples`` for runs that never cross.
    """
    below = x < threshold
    first: IntArray = np.argmax(below, axis=0).astype(np.intp)
    first[~below.any(axis=0)] = x.shape[0]
    return first
