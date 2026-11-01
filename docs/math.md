# Mathematics of the model and of the early-warning indicators

This note derives every formula used in the code. It is self-contained: it assumes calculus, basic probability and complex numbers. Numbers quoted here are either exact consequences of the formulas or reference values used as test oracles.

Contents: [1 Model](#1-model-and-potential) · [2 Equilibria](#2-equilibria) · [3 Stability and the fold](#3-stability-and-the-fold) · [4 Hysteresis](#4-hysteresis) · [5 Noise](#5-stochastic-extension) · [6 Linearisation to OU](#6-linearisation-to-an-ornstein-uhlenbeck-process) · [7 Statistics](#7-the-statistics) · [8 Noise-induced tipping](#8-noise-induced-tipping-and-limitations)

## 1. Model and potential

The deterministic model is the one-dimensional flow

$$
\dot x = f(x,r) = r + x - x^{3},
$$

with state $x$ and control parameter $r$. It is the gradient flow of the potential

$$
V(x,r) = -rx - \frac{x^{2}}{2} + \frac{x^{4}}{4}, \qquad f = -\frac{\partial V}{\partial x}.
$$

Along a solution $\dot V = \frac{\partial V}{\partial x}\dot x = -f^{2} \le 0$, so $x$ always slides downhill and the only possible long-time behaviour is convergence to an equilibrium (no oscillations in one dimension). For $r = 0$ the potential is the symmetric double well $-x^2/2 + x^4/4$ with minima at $x = \pm 1$. The term $-rx$ tilts the landscape: $r > 0$ deepens the right well, $r < 0$ the left well. This is the imperfect pitchfork: the symmetric pitchfork at $r=0$ unfolded by the tilt $r$.

## 2. Equilibria

Equilibria satisfy $f(x,r) = 0$, that is the depressed cubic

$$
x^{3} + px + q = 0, \qquad p = -1,\quad q = -r.
$$

### Number of real roots

The discriminant of $x^3 + px + q$ is $\Delta = -(4p^{3} + 27q^{2})$. Here

$$
\Delta = 4 - 27r^{2}.
$$

There are three distinct real roots iff $\Delta > 0$, that is

$$
\lvert r\rvert < r_c = \frac{2}{3\sqrt{3}} \approx 0.3849,
$$

since $r_c^2 = 4/27$. At $\lvert r\rvert = r_c$ two roots coincide; for $\lvert r\rvert > r_c$ there is one real root and a complex-conjugate pair.

### Trigonometric form (three real roots)

Substitute $x = m\cos\theta$. Using $\cos 3\theta = 4\cos^{3}\theta - 3\cos\theta$, the cubic $x^3 - x - r = 0$ becomes

$$
m^{3}\cos^{3}\theta - m\cos\theta = r .
$$

Choose $m$ so that the coefficients are in the ratio $4:3$, that is $m^{3}/4 = m/3$, giving $m^2 = 4/3$ and $m = 2/\sqrt{3}$. Then the left-hand side equals $\frac{m}{3}\cos 3\theta$ and

$$
\cos 3\theta = \frac{3r}{m} = \frac{3\sqrt{3}}{2}\,r .
$$

All three roots follow from the three branches of the inverse cosine:

$$
x_k = \frac{2}{\sqrt{3}}\cos\!\left(\frac{1}{3}\arccos\!\Big(\frac{3\sqrt{3}}{2}\,r\Big) - \frac{2\pi k}{3}\right), \qquad k = 0,1,2,
$$

with $x_0$ the largest root. The argument of the arccosine lies in $[-1, 1]$ iff $\lvert r\rvert \le \frac{2}{3\sqrt{3}} = r_c$. It reaches $\pm 1$ exactly at the fold, which is where two of the three cosines coincide: for $r = r_c$ the argument is $1$, $\arccos 1 = 0$, and $x_1 = x_2$ (the double root). Beyond the fold the argument leaves $[-1,1]$, the arccosine becomes complex, and the formula would have to be continued with hyperbolic functions; the code uses Cardano instead.

### Cardano (one real root)

For the depressed cubic set $x = u + v$. Then $x^3 = u^3 + v^3 + 3uv(u+v)$, so the cubic becomes

$$
u^{3} + v^{3} + (3uv + p)(u+v) + q = 0 .
$$

Impose $uv = -p/3$ (here $uv = 1/3$). The middle term vanishes and $u^3 + v^3 = -q = r$, while $u^3 v^3 = -p^3/27 = 1/27$. Hence $u^3$ and $v^3$ are the roots of $z^2 - rz + 1/27 = 0$:

$$
u^{3},\, v^{3} = \frac{r}{2} \pm \sqrt{\frac{r^{2}}{4} - \frac{1}{27}} .
$$

For $\lvert r\rvert > r_c$ the radicand is positive, $u^3$ and $v^3$ are real, and with real cube roots

$$
x = \sqrt[3]{\frac{r}{2} + \sqrt{\frac{r^{2}}{4} - \frac{1}{27}}} + \sqrt[3]{\frac{r}{2} - \sqrt{\frac{r^{2}}{4} - \frac{1}{27}}} .
$$

Implementation note: compute the real cube root with `numpy.cbrt`. The expression `a ** (1/3)` returns the principal complex root for negative `a` and produces the wrong branch.

### Worked example at $r = 0$ (complex arithmetic)

At $r=0$ the radicand is $-1/27 < 0$, so $u^3$ is purely imaginary:

$$
u^{3} = \sqrt{-\tfrac{1}{27}} = \frac{i}{3\sqrt{3}}, \qquad \lvert u^{3}\rvert = \frac{1}{3\sqrt{3}}, \qquad \arg u^{3} = \frac{\pi}{2}.
$$

Take the principal cube root: modulus $\lvert u\rvert = (3\sqrt{3})^{-1/3} = 1/\sqrt{3}$ and argument $\pi/6$:

$$
u = \frac{1}{\sqrt{3}}\left(\cos\frac{\pi}{6} + i\sin\frac{\pi}{6}\right) = \frac{1}{\sqrt{3}}\left(\frac{\sqrt{3}}{2} + \frac{i}{2}\right) = 0.5 + 0.2887\,i .
$$

The partner with $uv = 1/3$ is the conjugate, $v = \bar u = 0.5 - 0.2887\,i$. Check: $uv = \lvert u\rvert^2 = 1/3$. The first root is

$$
x_0 = u + v = 2\,\mathrm{Re}\,u = 1 .
$$

The other two roots use the cube roots of unity $\omega = e^{2\pi i/3}$, namely $x = \omega u + \omega^{2} v = 2\,\mathrm{Re}(\omega u)$ and $x = \omega^{2}u + \omega v = 2\,\mathrm{Re}(\omega^{2}u)$:

$$
2\,\mathrm{Re}(\omega u) = \frac{2}{\sqrt{3}}\cos\frac{5\pi}{6} = -1, \qquad 2\,\mathrm{Re}(\omega^{2} u) = \frac{2}{\sqrt{3}}\cos\frac{3\pi}{2} = 0 .
$$

The roots are $-1, 0, 1$, as expected from $x^3 - x = x(x-1)(x+1)$. They coincide with the trigonometric form at $r=0$: $\arccos 0 = \pi/2$, and $\frac{2}{\sqrt 3}\cos(\pi/6 - 2\pi k/3)$ gives $1, 0, -1$ for $k=0,1,2$. In the regime of three real roots Cardano needs complex intermediate numbers even though the result is real (the casus irreducibilis), which is why the trigonometric form is used there.

## 3. Stability and the fold

The growth rate of a small perturbation $y = x - x^*$ of an equilibrium is

$$
\lambda(x^*) = \frac{\partial f}{\partial x}\Big|_{x^*} = 1 - 3x^{*2}.
$$

An equilibrium is stable iff $\lambda < 0$, that is $\lvert x^*\rvert > 1/\sqrt{3}$. For $\lvert r\rvert < r_c$ the outer roots are stable and the middle root is unstable. Reference values on the upper branch: $r=0$: $x^*=1.0000$, $\lambda=-2.0000$; $r=-0.2$: $0.8789$, $-1.3173$; $r=-0.3$: $0.7865$, $-0.8557$; $r=-0.35$: $0.7140$, $-0.5294$; $r=-0.38$: $0.6298$, $-0.1898$. At $r=0.2$ the roots are $-0.8789,\,-0.2091,\,1.0880$.

### Taylor expansion at the fold

At $r = -r_c$ the upper stable root meets the unstable one at $x_c = 1/\sqrt{3}$, where $f = 0$ and $f_x = 1 - 3x_c^2 = 0$. The other stable root is $-2/\sqrt{3}$. The remaining derivatives at $(x_c, -r_c)$ are

$$
f_r = 1, \qquad f_{xx} = -6x_c = -2\sqrt{3}, \qquad f_{xxx} = -6 .
$$

With $y = x - x_c$ and $\mu = r + r_c$, the Taylor expansion to leading order is

$$
\dot y = \mu - \sqrt{3}\,y^{2} + O(\mu y,\; y^{3}),
$$

the normal form of the saddle-node bifurcation $\dot y = \mu - a y^2$ with $a = \sqrt{3}$. For $\mu > 0$ it has equilibria $y_\pm = \pm\sqrt{\mu/\sqrt{3}}$, with growth rate

$$
\lambda(y_\pm) = -2\sqrt{3}\,y_\pm = \mp\, 2\cdot 3^{1/4}\sqrt{\mu}.
$$

So $y_+$ (the upper stable branch) has $\lambda \approx -2\cdot 3^{1/4}\sqrt{\mu}$ and $y_-$ (the unstable root) has the opposite sign. This reproduces the reference value at $r=-0.38$ to within a few per cent. For $\mu < 0$ there are no equilibria near $x_c$, and for $\mu = 0$ there is a single one, $y=0$, with $\lambda = 0$.

Consequence for the early-warning signals: the stable growth rate vanishes like a square root,

$$
\lvert\lambda\rvert \propto \sqrt{r + r_c} \quad\Rightarrow\quad \operatorname{Var} = \frac{\sigma^{2}}{2\lvert\lambda\rvert} \propto (r + r_c)^{-1/2}.
$$

### Half-stable point at the bifurcation

At $\mu=0$ the equation is $\dot y = -\sqrt{3}\,y^{2}$. The fixed point $y=0$ attracts from the side $y>0$ and repels towards $y<0$: it is half-stable. It is the limit of the stable and unstable equilibria merging, and it is not structurally stable: for $\mu>0$ it splits into two, for $\mu<0$ it disappears. By the symmetry $x \to -x$, $r \to -r$ the fold at $r=+r_c$ is the mirror image, with double root $x=-1/\sqrt{3}$ and the other root at $+2/\sqrt{3}$.

### Why "saddle-node"

In one dimension the two colliding equilibria are a stable node and an unstable point. The name comes from the planar version

$$
\dot x = r + x^{2}, \qquad \dot y = -y .
$$

The Jacobian at an equilibrium is $\operatorname{diag}(2x,\,-1)$. For $r<0$ the equilibria are $x = \pm\sqrt{-r}$:

- $x = -\sqrt{-r}$: eigenvalues $2x < 0$ and $-1$, both negative, a stable node;
- $x = +\sqrt{-r}$: eigenvalues $2x > 0$ and $-1$, one positive and one negative, a saddle.

As $r \to 0^-$ the node and the saddle approach each other and collide at $r=0$ (eigenvalue $2x = 0$, half-stable); for $r>0$ they are gone. A saddle and a node annihilate, hence saddle-node. The word saddle point is reserved in this project for the two-dimensional equilibrium type; the event itself is called a saddle-node (fold, tangent) bifurcation.

## 4. Hysteresis

Let $r$ decrease slowly, starting on the upper branch. The system tracks $x_0(r)$, the largest root, which exists and is stable for all $r > -r_c$. At $r = -r_c$ this branch ends in the fold; the system must jump to the only remaining equilibrium, the lower branch near $x = -2/\sqrt{3} \approx -1.1547$. The jump size is $x_c - (-2/\sqrt3) = \sqrt{3}$.

Now let $r$ increase again. The system stays on the lower branch until that branch ends at $r = +r_c$, and then jumps up to about $+1.1547$. The jumps happen at different values of $r$, so the path depends on the history. In the interval $-r_c < r < r_c$ both branches are stable (bistability), and which one is occupied depends on where the system came from. The loop has width

$$
2r_c = \frac{4}{3\sqrt{3}} \approx 0.7698 .
$$

Practical consequence: after a tipping point it is not enough to return $r$ to its value at the fold; it has to be pushed past the other fold.

## 5. Stochastic extension

Add white noise to the flow, in the Langevin form

$$
\frac{dx}{dt} = f(x,r) + \sigma\,\xi(t), \qquad\text{written as}\qquad dx = f(x,r)\,dt + \sigma\,dW_t .
$$

Here $W_t$ is a Wiener process: $W_0 = 0$, the paths are continuous, increments over disjoint intervals are independent, and $W_{t+h} - W_t \sim \mathcal N(0, h)$. The white noise $\xi = dW/dt$ does not exist as an ordinary function, which is why the equation is written in differential form and understood as the integral equation

$$
x_t = x_0 + \int_0^t f(x_s, r_s)\,ds + \sigma W_t .
$$

The noise is additive (its amplitude $\sigma$ does not depend on $x$), so the Itô and Stratonovich interpretations coincide.

### Euler–Maruyama and the $\sqrt{\Delta t}$

On a grid $t_n = n\,\Delta t$, the Euler–Maruyama scheme is

$$
x_{n+1} = x_n + f(x_n, r_n)\,\Delta t + \sigma\sqrt{\Delta t}\;\eta_n, \qquad \eta_n \sim \mathcal N(0,1)\ \text{i.i.d.}
$$

The factor $\sqrt{\Delta t}$ follows from $\operatorname{Var}(W_{t+\Delta t} - W_t) = \Delta t$: the variance of the accumulated noise must grow linearly in time, independently of the step size. Using $\Delta t\,\eta_n$ would give a variance of order $\Delta t^2$ per step, and the noise would vanish as the grid is refined; using a fixed amplitude per step would make the result depend on the grid. With $\sqrt{\Delta t}$, $n$ steps of total time $T = n\Delta t$ accumulate variance $\sigma^2 T$ regardless of $n$. For additive noise the scheme converges with strong order 1 (the Milstein correction vanishes because $\sigma$ is constant).

## 6. Linearisation to an Ornstein–Uhlenbeck process

Near a stable equilibrium $x^*(r)$ with $r$ held fixed, write $x = x^* + y$ and expand $f$:

$$
f(x^*+y, r) = \lambda\,y + \tfrac12 f_{xx}\,y^{2} + \dots, \qquad \lambda = 1 - 3x^{*2} < 0 .
$$

Dropping the quadratic and higher terms gives the Ornstein–Uhlenbeck (OU) process (Uhlenbeck and Ornstein, 1930)

$$
dy = \lambda\,y\,dt + \sigma\,dW_t .
$$

### Solution by integrating factor

Multiply by $e^{-\lambda t}$. By the product rule (there is no Itô correction because $e^{-\lambda t}$ is deterministic),

$$
d\!\left(e^{-\lambda t}y_t\right) = \sigma e^{-\lambda t}\,dW_t
\quad\Rightarrow\quad
y_t = e^{\lambda t}y_0 + \sigma\int_0^t e^{\lambda (t-s)}\,dW_s .
$$

The stochastic integral is a Gaussian with mean zero, so $y_t$ is Gaussian with mean $e^{\lambda t}y_0 \to 0$.

### Variance by the Itô isometry

The Itô isometry states $\mathbb E\big[(\int_0^t g(s)\,dW_s)^2\big] = \int_0^t g(s)^2\,ds$. Hence

$$
\operatorname{Var}(y_t) = \sigma^{2}\int_0^t e^{2\lambda(t-s)}\,ds = \frac{\sigma^{2}}{2\lvert\lambda\rvert}\left(1 - e^{-2\lvert\lambda\rvert t}\right)
\;\xrightarrow{t\to\infty}\; \frac{\sigma^{2}}{2\lvert\lambda\rvert}.
$$

### Variance balance (heuristic check)

Apply the chain rule of Itô calculus to $y^2$: $d(y^2) = 2y\,dy + \sigma^2 dt$. Taking expectations with $\mathbb E[y]=0$,

$$
\frac{d}{dt}\operatorname{Var}(y) = 2\lambda\operatorname{Var}(y) + \sigma^{2}.
$$

Restoring force removes variance at rate $2\lvert\lambda\rvert\operatorname{Var}$, noise injects it at rate $\sigma^2$. The balance is reached at $\operatorname{Var} = \sigma^2/(2\lvert\lambda\rvert)$, in agreement with the isometry result. As $\lvert\lambda\rvert \to 0$ the removal weakens and the variance grows.

### Autocorrelation function and AR(1)

For $\tau \ge 0$ in the stationary regime, $y_{t+\tau} = e^{\lambda\tau}y_t + (\text{noise independent of } y_t)$, so

$$
\operatorname{Cov}(y_t, y_{t+\tau}) = e^{\lambda\tau}\operatorname{Var}(y), \qquad \rho(\tau) = e^{\lambda\tau} = e^{-\lvert\lambda\rvert\tau}.
$$

The correlation time is $1/\lvert\lambda\rvert$: critical slowing down means this time diverges at the fold. Sampled at the interval $\Delta t$, the process satisfies exactly the AR(1) recursion

$$
y_{n+1} = \phi\,y_n + \varepsilon_n, \qquad \phi = e^{\lambda\,\Delta t}, \qquad \operatorname{Var}(\varepsilon_n) = \frac{\sigma^{2}}{2\lvert\lambda\rvert}\left(1-\phi^{2}\right).
$$

Given an estimate $\hat\phi \in (0,1)$ of the lag-1 autocorrelation, the recovery rate is estimated by

$$
\hat\theta = -\frac{\ln\hat\phi}{\Delta t}, \qquad \theta = \lvert\lambda\rvert .
$$

Reference values for $\sigma = 0.05$ and $\Delta t = 0.5$:

| $r$ | $\lvert\lambda\rvert$ | variance $\sigma^2/(2\lvert\lambda\rvert)$ | AR(1) $\phi$ |
| --- | --- | --- | --- |
| 0 | 2.0000 | 0.000625 | 0.3679 |
| -0.2 | 1.3173 | 0.00095 | 0.5175 |
| -0.3 | 0.8557 | 0.00146 | 0.6519 |
| -0.35 | 0.5294 | 0.00236 | 0.7674 |
| -0.38 | 0.1898 | 0.00659 | 0.9095 |

### Where the linearisation holds

The OU result is the $\sigma \to 0$ limit: the fluctuations must stay in a region where the quadratic term of $f$ is negligible compared with $\lambda y$, that is $\lvert f_{xx}\,y/2\rvert \ll \lvert\lambda\rvert$ with $y \sim \sigma/\sqrt{2\lvert\lambda\rvert}$. Because $\lvert\lambda\rvert \to 0$ at the fold while $f_{xx}$ does not, the condition is violated close enough to the fold for any fixed $\sigma$. The simulation confirms both the agreement at moderate parameters and the departure near the fold:

- at $r=0$, $\sigma=0.05$: simulated variance 0.00063 against 0.00063 predicted, AR(1) 0.364 against 0.368;
- at $r=-0.33$ the ratio of simulated to predicted variance is 1.084 for $\sigma=0.05$, 1.021 for $\sigma=0.03$ and 0.997 for $\sigma=0.015$.

The ratio tends to 1 as $\sigma \to 0$. The sampled AR(1) formula also assumes $r$ is frozen; during a ramp the equilibrium moves, which is the reason for the detrending step below.

## 7. The statistics

A trajectory is a series $x_1, \dots, x_n$ sampled every $\Delta t$ (0.5 in the baseline). The pipeline turns each run into one number per indicator and then compares the ramp group with the control group.

**Detrending.** The slow movement of the equilibrium $x^*(r(t))$ would be mistaken for fluctuation. The residual is $x_i$ minus its uniform moving average over `detrend_window` samples (edges handled with `mode="nearest"`). This is a high-pass filter. Too short a window removes the slow fluctuations that carry the signal; too long a window leaves the trend in.

**Rolling indicators.** In a window of $W$ samples the variance and the lag-1 autocorrelation of the residual are computed:

$$
\widehat{\operatorname{Var}} = \frac{1}{W-1}\sum_{i}(e_i-\bar e)^2, \qquad
\hat\phi = \operatorname{corr}(e_i,\,e_{i+1}),
$$

both computed over the trailing window ending at the current sample.

The default window is 10% of the ramp, $W = \max(10, \operatorname{round}(0.10\,T/\Delta t))$, with the detrending window $\max(5, W//4)$.

**Kendall tau.** The trend of an indicator $s_1,\dots,s_m$ against time is measured with Kendall's rank correlation

$$
\tau = \frac{C - D}{\binom{m}{2}}
$$

(with the tie-corrected variant when needed), where $C$ and $D$ count concordant and discordant pairs. It is invariant under monotone transforms and robust to outliers. The indicator series is subsampled every $\max(\lfloor W/40\rfloor, 1)$ samples, starting at $W$, to reduce the overlap of consecutive windows. The analysis of each run stops before the tip: at $\min(\text{tip index} - \text{detrend window},\ \operatorname{round}(0.6\,n))$, where a tip is the first sample with $x<0$. Runs with fewer than 15 usable subsampled points are invalid.

**AUC.** Let $\tau^{\text{ramp}}_j$ and $\tau^{\text{null}}_k$ be the tau values of the two groups. The area under the ROC curve is the Mann–Whitney probability

$$
\mathrm{AUC} = P(\tau^{\text{ramp}} > \tau^{\text{null}}) + \tfrac12 P(\tau^{\text{ramp}} = \tau^{\text{null}}).
$$

AUC $=0.5$ means no discrimination, AUC $=1$ perfect separation.

**TPR at 5% FPR.** Take the 95th percentile of the control taus as the alarm threshold, so that 5% of control runs raise a false alarm, and report $\mathrm{TPR} = \operatorname{mean}(\tau^{\text{ramp}} > \text{threshold})$. This is the more operational metric: it answers how often a ramp run is flagged when false alarms are limited to 5%.

### Why a control group is mandatory

The rolling indicators are computed on overlapping windows, so consecutive values are strongly dependent and the effective number of independent points in a tau is far smaller than $m$. A noise-driven series that is itself autocorrelated, such as an OU process, wanders: its rolling variance and rolling AR(1) show apparent trends even when nothing changes. The Kendall tau of such a series against time is therefore not tightly concentrated around zero, and the usual p-value for $\tau$ (which assumes independent points) is far too optimistic. A tau of 0.3 can be unremarkable under the null.

The only reliable reference is the empirical distribution of tau under the null, produced by the same pipeline on the same noise with $r$ held constant. The control group provides this, and the 5%-FPR threshold is read from it. With a single real time series there is no control group, so false-positive rates cannot be estimated, which is one of the limitations listed below. The control must also be monitored for tipping: at large $\sigma$ even control runs cross $x<0$ by noise, which is reported as `frac_null_tipped`.

## 8. Noise-induced tipping and limitations

Three routes to a tipping point are distinguished (Ashwin et al., 2012): bifurcation-induced (a control parameter crosses a fold), noise-induced (fluctuations carry the system over a barrier while the parameter is still in the bistable range) and rate-induced (the parameter changes too quickly for the system to track the moving equilibrium). Early-warning signals based on critical slowing down address only the first.

In the bistable range the system can escape the upper well by noise. For the gradient system $dx = -V'(x)\,dt + \sigma\,dW$, Kramers' formula gives an escape rate that depends on the barrier $\Delta V$ as

$$
k \propto \exp\!\left(-\frac{2\,\Delta V}{\sigma^{2}}\right).
$$

Near the fold the normal form $\dot y = \mu - \sqrt{3}y^2$ has potential $-\mu y + y^{3}/\sqrt{3}$, and the barrier between the stable and unstable roots is

$$
\Delta V = \frac{4}{3}\,3^{-1/4}\,\mu^{3/2} \quad\to\quad 0 \text{ as } \mu \to 0 .
$$

The barrier relative to the stationary variance, $\Delta V / \operatorname{Var}$, scales like $\mu^{2}$ and vanishes at the fold, so for any fixed $\sigma$ the escape becomes likely before $r$ reaches $-r_c$. Simulations show this: near $r=-0.35$ with $\sigma=0.05$ over long times, runs escape. For large $\sigma$ the system tips by noise long before the fold; in the preliminary sweep essentially all ramp runs tip before 60% of the ramp at $\sigma=0.15$, and at $\sigma=0.30$ most control runs tip at duration 2000. The early-warning signal can then be present in the statistics and still be useless, because the system leaves the branch before the signal builds.

Limitations to keep in mind when reading the results:

- the model is a toy with known ground truth, and there is no real data; one real series cannot estimate false-positive rates;
- survivor bias: runs that tip early are truncated, and the analysed set is not a random sample of runs;
- AUC does not say whether the alarm comes early enough to be useful;
- linear OU theory degrades near the fold and at large $\sigma$;
- the indicators show that the system approaches a fold, not when it will tip;
- the outcome depends on analyst choices such as the window length and the detrending.
