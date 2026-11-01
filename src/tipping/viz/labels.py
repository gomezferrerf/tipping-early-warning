# ruff: noqa: RUF001  (Greek letters and typographic dashes are intended in figure text)
"""Bilingual text for every static figure.

All strings that appear in a figure live here, keyed by a short identifier and available in
Spanish (the talk) and English (the README). Numbers that depend on the data are written as
``{placeholders}`` and filled in by :func:`text`. Terminology follows the project glossary:
"punto de quiebre" for tipping point and "bifurcación silla-nodo" for the saddle-node event.
"""

from __future__ import annotations

from tipping.viz.style import Lang

LANGS: tuple[Lang, ...] = ("es", "en")

LABELS: dict[str, dict[str, str]] = {
    # --- generic symbols and axes -------------------------------------------------------
    "axis_x": {"es": "x", "en": "x"},
    "axis_potential": {"es": "V", "en": "V"},
    "axis_r": {"es": "r", "en": "r"},
    "axis_xstar": {"es": "x*", "en": "x*"},
    "time": {"es": "tiempo", "en": "time"},
    "runs": {"es": "corridas", "en": "runs"},
    # --- landscapes / bifurcation diagram ----------------------------------------------
    "r_caption": {"es": "r = {r}", "en": "r = {r}"},
    "stable": {"es": "estable", "en": "stable"},
    "unstable": {"es": "inestable", "en": "unstable"},
    "semistable": {"es": "semiestable", "en": "semistable"},
    "bistable": {"es": "biestable", "en": "bistable"},
    "fold_left": {"es": "r = −2/(3√3)\n≈ −0,385", "en": "r = −2/(3√3)\n≈ −0.385"},
    "fold_right": {"es": "r = +2/(3√3)\n≈ +0,385", "en": "r = +2/(3√3)\n≈ +0.385"},
    "r_decreasing": {"es": "r disminuye", "en": "r decreasing"},
    "r_increasing": {"es": "r aumenta", "en": "r increasing"},
    "loop_width": {"es": "ancho del lazo $2r_c$ ≈ {width}", "en": "loop width $2r_c$ ≈ {width}"},
    # --- noise ---------------------------------------------------------------------------
    "no_noise": {"es": "sin ruido", "en": "without noise"},
    "with_noise": {"es": "con ruido, σ = {sigma}", "en": "with noise, σ = {sigma}"},
    "equilibrium": {"es": "x* = 1", "en": "x* = 1"},
    # --- critical slowing down (s10) ---------------------------------------------------------
    "deviation": {"es": "x − x*", "en": "x − x*"},
    "deviation_title": {"es": "desviación del equilibrio", "en": "deviation from equilibrium"},
    "distribution_title": {"es": "distribución", "en": "distribution"},
    "autocorr_title": {"es": "autocorrelación", "en": "autocorrelation"},
    "lag": {"es": "retardo τ", "en": "lag τ"},
    "valley_steep": {
        "es": "valle empinado\n(r = {r}, λ = {lam})",
        "en": "steep valley\n(r = {r}, λ = {lam})",
    },
    "valley_flat": {
        "es": "valle plano\n(r = {r}, λ ≈ {lam})",
        "en": "flat valley\n(r = {r}, λ ≈ {lam})",
    },
    "lam_steep": {"es": "λ = {lam}", "en": "λ = {lam}"},
    "lam_flat": {"es": "λ ≈ {lam}", "en": "λ ≈ {lam}"},
    "theory_ou": {"es": "teoría (OU)", "en": "theory (OU)"},
    # --- experiment (s11) and results (s12, s13) -------------------------------------------
    "ramp": {"es": "rampa", "en": "ramp"},
    "control": {"es": "control", "en": "control"},
    "ramp_series": {"es": "rampa: r de 0 a −0,6", "en": "ramp: r from 0 to −0.6"},
    "control_series": {"es": "control: r = 0", "en": "control: r = 0"},
    "fold_time": {
        "es": "pliegue (r = −$r_c$) · t ≈ {t}",
        "en": "fold (r = −$r_c$) · t ≈ {t}",
    },
    "rolling_variance": {
        "es": "varianza móvil ($\\times 10^{-3}$)",
        "en": "rolling variance ($\\times 10^{-3}$)",
    },
    "rolling_ar1": {"es": "AR(1) móvil", "en": "rolling AR(1)"},
    "band_10_90": {"es": "percentiles 10–90 %", "en": "10–90% percentiles"},
    "kendall_ar1": {"es": "τ de Kendall del AR(1)", "en": "Kendall τ of the AR(1)"},
    "threshold": {"es": "umbral: 5 % de\nfalsos positivos", "en": "threshold: 5%\nfalse positives"},
    "auc": {"es": "AUC = {auc}", "en": "AUC = {auc}"},
    # --- heatmaps (s14, b04) -------------------------------------------------------------------
    "heat_ar1": {"es": "AR(1)", "en": "AR(1)"},
    "heat_variance": {"es": "varianza", "en": "variance"},
    "heat_x": {"es": "duración de la rampa: corta → larga", "en": "ramp duration: short → long"},
    "heat_y": {"es": "ruido σ", "en": "noise σ"},
    "heat_colorbar": {"es": "AUC medio", "en": "mean AUC"},
    "unreliable": {"es": "el control cae solo", "en": "the control tips on its own"},
    "ramp_early": {
        "es": "la mayoría de las rampas cae antes del 60 % del recorrido",
        "en": "most ramps tip before 60 % of the ramp",
    },
    "tipped_null": {"es": "control que cae solo", "en": "control runs that tip"},
    "tipped_ramp": {"es": "rampa que cae antes de tiempo", "en": "ramp runs that tip too early"},
    "tipped_colorbar": {"es": "fracción de corridas", "en": "fraction of runs"},
    # --- README titles (slides never use them) -------------------------------------------------
    "title_bifurcation": {
        "es": "Ruta a la bifurcación silla-nodo: el valle se aplana y desaparece",
        "en": "Route to the saddle-node bifurcation: the valley flattens and vanishes",
    },
    "title_signal": {
        "es": "Desaceleración crítica: valle plano, fluctuaciones más grandes y lentas",
        "en": "Critical slowing down: a flatter valley gives larger, slower fluctuations",
    },
    "title_results": {
        "es": "Rampa frente a control: las señales de alerta crecen antes del punto de quiebre",
        "en": "Ramp versus control: the warning signals grow before the tipping point",
    },
    "title_heatmap": {
        "es": "Cuándo funciona la alerta: AUC según la duración de la rampa y el ruido",
        "en": "When the warning works: AUC by ramp duration and noise level",
    },
}


def text(key: str, lang: Lang, **fields: object) -> str:
    """Return the label ``key`` in ``lang``, with ``{placeholders}`` filled from ``fields``.

    Parameters
    ----------
    key : str
        Label identifier, a key of :data:`LABELS`.
    lang : {"es", "en"}
        Language of the text.
    **fields
        Values for the placeholders of the label, if any.

    Returns
    -------
    str
        The formatted label.

    Raises
    ------
    KeyError
        If ``key`` is unknown (the message lists the offending key).
    """
    try:
        template = LABELS[key][lang]
    except KeyError as error:
        msg = f"unknown label key or language: {key!r}, {lang!r}"
        raise KeyError(msg) from error
    return template.format(**fields) if fields else template
