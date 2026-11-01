"""Build the Spanish talk deck (python-pptx) and export it to PDF with LibreOffice.

Run with ``uv run python deck/build_deck.py``. Outputs go to ``deck/build/``:
``tipping_puntos_de_quiebre.pptx`` and, when LibreOffice is installed, the same name as PDF.

Inputs: figures in ``results/figures/es/``, animations in ``results/animations/es/``,
numbers from ``results/key_numbers.json`` (never typed by hand) and, if present, speaker
notes from ``deck/notes.json`` (``{"1": "...", ..., "B1": "..."}``).

Videos are embedded with a poster frame. PowerPoint plays them on click (no autoplay
XML is injected); LibreOffice and PDF exports only show the poster.
"""

# ruff: noqa: RUF001, RUF002  (Unicode math symbols in slide text are intentional)
from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as PresentationType
from pptx.shapes.base import BaseShape
from pptx.shapes.picture import Picture
from pptx.slide import Slide
from pptx.text.text import TextFrame
from pptx.util import Emu, Pt

from tipping.paths import project_root, results_dir
from tipping.viz.style import PALETTE

# --------------------------------------------------------------------------- constants
FONT = "Calibri"
SLIDE_W = 13.333
SLIDE_H = 7.5
MARGIN = 0.7
CONTENT_W = SLIDE_W - 2 * MARGIN
TITLE_Y = 0.45
TITLE_H = 0.95
TITLE_PT = 36
CONTENT_TOP = 1.55
CONTENT_BOTTOM = 6.85
FOOTER_Y = 7.02
FOOTER_H = 0.3
FOOTER_PT = 12
BODY_PT = 28
SMALL_PT = 24
FORMULA_PT = 32
VIDEO_ASPECT = 16 / 9
TITLE_ONLY_LAYOUT = 5
FOOTER_TEXT = "Fernando · Sistemas Complejos"
OUT_NAME = "tipping_puntos_de_quiebre"

INK = PALETTE.ink
MUTED = PALETTE.muted
BG = PALETTE.background
GRID = PALETTE.grid

ROOT = project_root()
DECK_DIR = ROOT / "deck"
BUILD_DIR = DECK_DIR / "build"
FIG_DIR = results_dir() / "figures" / "es"
ANIM_DIR = results_dir() / "animations" / "es"
NOTES_PATH = DECK_DIR / "notes.json"
KEY_NUMBERS_PATH = results_dir() / "key_numbers.json"

_MARKUP = re.compile(r"(\*\*[^*]+\*\*|\^\{[^}]*\}|_\{[^}]*\})")


# --------------------------------------------------------------------------- helpers
def rgb(hex_color: str) -> RGBColor:
    """Convert ``#RRGGBB`` to an ``RGBColor``."""
    return RGBColor.from_string(hex_color.lstrip("#").upper())


def inch(value: float) -> Emu:
    """Inches to EMU (float friendly)."""
    return Emu(round(value * 914400))


def fmt_es(value: float, decimals: int = 2) -> str:
    """Format a number with a Spanish decimal comma, never rounding up to ``1,00``.

    Two decimals by default; if that would show ``1,00`` for a value that is not exactly 1
    (e.g. 0.9998), switch to four decimals so the slide does not overstate the result.
    """
    text = f"{value:.{decimals}f}"
    if float(text) == 1.0 and value != 1.0 and value < 1.0:
        text = f"{value:.4f}"
    return text.replace(".", ",")


def load_key_numbers() -> dict[str, Any]:
    """Read ``results/key_numbers.json`` (single source of truth for every number)."""
    data: dict[str, Any] = json.loads(KEY_NUMBERS_PATH.read_text(encoding="utf-8"))
    return data


def sweep_cell(kn: dict[str, Any], sigma: float, duration: float) -> dict[str, Any]:
    """Return the sweep-summary row for one (sigma, duration) cell."""
    for row in kn["sweep_summary"]["rows"]:
        if math.isclose(row["sigma"], sigma) and math.isclose(row["duration"], duration):
            cell: dict[str, Any] = row
            return cell
    raise KeyError((sigma, duration))


def sweep_axis(kn: dict[str, Any], key: str) -> list[float]:
    """Sorted unique values of ``sigma`` or ``duration`` in the sweep summary."""
    return sorted({float(row[key]) for row in kn["sweep_summary"]["rows"]})


def load_notes() -> dict[str, str]:
    """Read optional speaker notes; returns an empty dict when the file is absent."""
    if not NOTES_PATH.exists():
        return {}
    raw = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.items()}


def _style_run(
    run: Any,
    size: float,
    color: str,
    *,
    bold: bool = False,
    italic: bool = False,
    script: str | None = None,
) -> None:
    font = run.font
    font.name = FONT
    font.size = Pt(size)
    font.bold = bold
    font.italic = italic
    font.color.rgb = rgb(color)
    if script == "sup":
        run.font._element.set("baseline", "30000")
    elif script == "sub":
        run.font._element.set("baseline", "-25000")


def _fill_paragraph(
    paragraph: Any,
    text: str,
    size: float,
    color: str,
    *,
    bold: bool = False,
    italic: bool = False,
) -> None:
    """Fill a paragraph from light markup: ``**bold**``, ``^{sup}``, ``_{sub}``."""
    for part in _MARKUP.split(text):
        if not part:
            continue
        run = paragraph.add_run()
        if part.startswith("**"):
            run.text = part[2:-2]
            _style_run(run, size, color, bold=True, italic=italic)
        elif part.startswith("^{"):
            run.text = part[2:-1]
            _style_run(run, size, color, bold=bold, italic=italic, script="sup")
        elif part.startswith("_{"):
            run.text = part[2:-1]
            _style_run(run, size, color, bold=bold, italic=italic, script="sub")
        else:
            run.text = part
            _style_run(run, size, color, bold=bold, italic=italic)


def _prepare_frame(frame: TextFrame, anchor: MSO_ANCHOR) -> None:
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = anchor


def add_text(
    slide: Slide,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str | Sequence[str],
    size: float = BODY_PT,
    color: str = INK,
    *,
    bold: bool = False,
    italic: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
    space_after: float = 0,
    name: str | None = None,
) -> BaseShape:
    """Add a text box (one paragraph per string) with zero internal margins."""
    box = slide.shapes.add_textbox(inch(x), inch(y), inch(w), inch(h))
    if name:
        box.name = name
    frame = box.text_frame
    _prepare_frame(frame, anchor)
    lines = [text] if isinstance(text, str) else list(text)
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_after = Pt(space_after)
        _fill_paragraph(paragraph, line, size, color, bold=bold, italic=italic)
    return box


def _drop_theme_effects(shape: Any) -> None:
    """Zero the style's effect reference so no renderer adds a theme shadow."""
    for ref in shape._element.xpath(".//a:effectRef"):
        ref.set("idx", "0")


def add_shape(
    slide: Slide,
    kind: MSO_SHAPE,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str | None,
    line: str | None = None,
    line_pt: float = 1.5,
    dashed: bool = False,
    name: str | None = None,
) -> Any:
    """Add an auto shape without shadow; ``fill=None`` leaves it transparent."""
    shape = slide.shapes.add_shape(kind, inch(x), inch(y), inch(w), inch(h))
    if name:
        shape.name = name
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(line_pt)
        if dashed:
            shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    shape.shadow.inherit = False
    _drop_theme_effects(shape)
    return shape


def shape_text(
    shape: Any,
    text: str | Sequence[str],
    size: float,
    color: str = INK,
    *,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.CENTER,
    anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
    margin: float = 0.12,
) -> None:
    """Write text inside an auto shape."""
    frame = shape.text_frame
    _prepare_frame(frame, anchor)
    frame.margin_left = frame.margin_right = inch(margin)
    lines = [text] if isinstance(text, str) else list(text)
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.alignment = align
        _fill_paragraph(paragraph, line, size, color, bold=bold)


def set_alt(shape: BaseShape, descr: str) -> None:
    """Set the accessibility description of a picture or video."""
    shape._element.xpath(".//p:cNvPr")[0].set("descr", descr)


# --------------------------------------------------------------------------- presentation
def new_presentation() -> PresentationType:
    """Create a 16:9 presentation with a cream master and rescaled layouts."""
    prs = Presentation()
    old_w = prs.slide_width
    prs.slide_width = inch(SLIDE_W)
    prs.slide_height = inch(SLIDE_H)
    factor = prs.slide_width / old_w
    holders = [prs.slide_master, *prs.slide_layouts]
    for holder in holders:
        for shape in holder.shapes:
            shape.left = int(shape.left * factor)
            shape.width = int(shape.width * factor)
    for holder in holders:
        holder.background.fill.solid()
        holder.background.fill.fore_color.rgb = rgb(BG)
    layout = prs.slide_layouts[TITLE_ONLY_LAYOUT]
    for holder in layout.placeholders:
        if holder.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            holder.left, holder.top = inch(MARGIN), inch(TITLE_Y)
            holder.width, holder.height = inch(CONTENT_W), inch(TITLE_H)
    core = prs.core_properties
    core.title = "¿Se puede ver venir un punto de quiebre?"
    core.author = "Fernando"
    core.subject = "Sistemas Complejos · Universidad EIA"
    stamp = dt.datetime(2026, 11, 1, 12, 0, 0)
    core.created = core.modified = stamp
    core.last_modified_by = "Fernando"
    return prs


def _slide_number_field(paragraph: Any, number: int) -> None:
    run = paragraph.add_run()
    run.text = str(number)
    _style_run(run, FOOTER_PT, MUTED)
    element = run._r
    element.tag = qn("a:fld")
    element.set("id", "{" + str(uuid.UUID(int=0x5EED0000 + number)).upper() + "}")
    element.set("type", "slidenum")


def add_footer(slide: Slide, number: int) -> None:
    """Footer: author left, slide number (live field) right, both muted."""
    add_text(
        slide, MARGIN, FOOTER_Y, 5.0, FOOTER_H, FOOTER_TEXT, FOOTER_PT, MUTED, name="Pie izquierdo"
    )
    box = add_text(
        slide, SLIDE_W - MARGIN - 1.0, FOOTER_Y, 1.0, FOOTER_H, "", FOOTER_PT, MUTED,
        align=PP_ALIGN.RIGHT, name="Número de diapositiva",
    )  # fmt: skip
    paragraph = box.text_frame.paragraphs[0]
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)
    _slide_number_field(paragraph, number)


def new_slide(
    prs: PresentationType,
    title: str | None,
    number: int,
    *,
    footer: bool = True,
    title_size: float = TITLE_PT,
    title_y: float = TITLE_Y,
) -> Slide:
    """Add a slide on the "Title Only" layout with explicit cream background and title."""
    slide = prs.slides.add_slide(prs.slide_layouts[TITLE_ONLY_LAYOUT])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BG)
    holder = slide.shapes.title
    assert holder is not None
    holder.left, holder.top = inch(MARGIN), inch(title_y)
    holder.width, holder.height = inch(CONTENT_W), inch(TITLE_H)
    frame = holder.text_frame
    _prepare_frame(frame, MSO_ANCHOR.MIDDLE)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = PP_ALIGN.LEFT
    _fill_paragraph(paragraph, title or "", title_size, INK, bold=True)
    if footer:
        add_footer(slide, number)
    return slide


def add_picture_fit(
    slide: Slide,
    path: Path,
    x: float,
    y: float,
    max_w: float,
    max_h: float,
    alt: str,
    *,
    center: bool = False,
) -> tuple[Picture, tuple[float, float, float, float]]:
    """Insert a picture scaled to fit a box, keeping aspect; returns it and its box (in)."""
    with Image.open(path) as img:
        aspect = img.width / img.height
    w = min(max_w, max_h * aspect)
    h = w / aspect
    left = x + (max_w - w) / 2 if center else x
    pic = slide.shapes.add_picture(str(path), inch(left), inch(y), inch(w), inch(h))
    pic.name = path.stem
    set_alt(pic, alt)
    return pic, (left, y, w, h)


def add_video(
    slide: Slide, video: Path, poster: Path, x: float, y: float, h: float, alt: str
) -> float:
    """Embed an MP4 with poster at height ``h`` (16:9); returns the width in inches."""
    w = h * VIDEO_ASPECT
    movie = slide.shapes.add_movie(
        str(video), inch(x), inch(y), inch(w), inch(h),
        poster_frame_image=str(poster), mime_type="video/mp4",
    )  # fmt: skip
    movie.name = video.stem
    set_alt(movie, alt)
    return w


# --------------------------------------------------------------------------- slide types
def figure_slide(
    prs: PresentationType,
    number: int,
    title: str,
    image: Path,
    alt: str,
    *,
    reserve: float = 0.0,
    below: Callable[[Slide, float], None] | None = None,
) -> Slide:
    """Title, one big figure and an optional row of text below it.

    ``reserve`` is the height (in) kept free under the figure; ``below(slide, y)`` draws
    into that band, with ``y`` the top of the band.
    """
    slide = new_slide(prs, title, number)
    avail = CONTENT_BOTTOM - CONTENT_TOP - reserve
    _, (_, fy, _, fh) = add_picture_fit(slide, image, MARGIN, CONTENT_TOP, CONTENT_W, avail, alt)
    if below is not None:
        below(slide, fy + fh + 0.2)
    return slide


def video_slide(
    prs: PresentationType,
    number: int,
    title: str,
    stem: str,
    alt: str,
    *,
    video_h: float = 5.3,
    x: float | None = None,
    y: float = CONTENT_TOP,
) -> tuple[Slide, float]:
    """Title plus an embedded video centred (or at ``x``). Returns the slide and video width."""
    slide = new_slide(prs, title, number)
    w = video_h * VIDEO_ASPECT
    left = (SLIDE_W - w) / 2 if x is None else x
    add_video(
        slide, ANIM_DIR / f"{stem}.mp4", ANIM_DIR / f"{stem}_poster.png", left, y, video_h, alt
    )
    return slide, w


def formula_rows(
    slide: Slide,
    rows: Sequence[tuple[str, str]],
    y0: float,
    *,
    size: float = 28,
    pitch: float = 0.82,
    label_w: float = 3.0,
) -> float:
    """Backup helper: muted label column + ink formula column. Returns the next free y."""
    y = y0
    for label, formula in rows:
        add_text(slide, MARGIN, y + 0.07, label_w, 0.5, label, 20, MUTED)
        add_text(
            slide, MARGIN + label_w + 0.2, y, CONTENT_W - label_w - 0.2, 0.7, formula, size, INK,
            anchor=MSO_ANCHOR.MIDDLE,
        )  # fmt: skip
        y += pitch
    return y


# --------------------------------------------------------------------------- the slides
def slide_01_hook(prs: PresentationType) -> Slide:
    """Build the hook: an almost empty slide with one tipping trajectory and the speaker line."""
    slide = new_slide(prs, "¿Se puede ver venir un punto de quiebre?", 1, footer=False, title_y=0.5)
    add_picture_fit(
        slide, FIG_DIR / "s01_hook.png", 3.0, 1.65, SLIDE_W - MARGIN - 3.0, 4.1,
        "Trayectoria ruidosa que baja lentamente y cae de golpe a otro valle.",
    )  # fmt: skip
    add_text(slide, MARGIN, 5.95, CONTENT_W, 0.55, "Fernando", 32, INK, bold=True, name="Nombre")
    add_text(
        slide, MARGIN, 6.55, CONTENT_W, 0.5,
        "Sistemas Complejos · Universidad EIA · 3 de noviembre de 2026", SMALL_PT, MUTED,
        name="Evento",
    )  # fmt: skip
    return slide


def slide_02_idea(prs: PresentationType) -> Slide:
    """Idea and goal as a three-step visual with native shapes."""
    slide = new_slide(prs, "Queremos ver la ruptura antes de que ocurra", 2)
    steps = [
        ("1", "Simular un sistema que se rompe", PALETTE.stable_fill, PALETTE.stable),
        ("2", "Medir señales antes de la ruptura", PALETTE.ramp_fill, PALETTE.ramp),
        ("3", "Comprobar si avisan, con control", PALETTE.control_fill, PALETTE.control),
    ]
    box_w, box_h, gap = 3.55, 3.4, (CONTENT_W - 3 * 3.55) / 2
    y = 2.1
    for i, (num, text, fill, deep) in enumerate(steps):
        x = MARGIN + i * (box_w + gap)
        card = add_shape(
            slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, box_w, box_h, fill=fill, name=f"Paso {num}"
        )
        card.adjustments[0] = 0.06
        badge = add_shape(
            slide, MSO_SHAPE.OVAL, x + 0.35, y + 0.35, 0.85, 0.85, fill=deep, name=f"Número {num}"
        )
        shape_text(badge, num, 32, "#FFFFFF", bold=True, margin=0)
        add_text(
            slide, x + 0.35, y + 1.5, box_w - 0.7, 1.3, text, BODY_PT, INK, name=f"Texto {num}"
        )
        if i < 2:
            arrow = add_shape(
                slide, MSO_SHAPE.RIGHT_ARROW, x + box_w + (gap - 0.5) / 2, y + box_h / 2 - 0.25,
                0.5, 0.5, fill=MUTED, name=f"Flecha {i + 1}",
            )  # fmt: skip
            arrow.adjustments[0] = 0.5
    return slide


def _jump_curve(width: float, height: float, n: int = 90) -> list[tuple[float, float]]:
    """Gentle slope followed by an abrupt drop, as screen points (inches)."""
    points = []
    for i in range(n + 1):
        t = i / n
        y = 0.06 + 0.12 * t + 0.74 / (1 + math.exp(-(t - 0.72) / 0.012))
        points.append((t * width, y * height))
    return points


def slide_03_tipping(prs: PresentationType) -> Slide:
    """Build "what is a tipping point": one sentence, a schematic jump and three example chips."""
    slide = new_slide(prs, "¿Qué es un punto de quiebre?", 3)
    add_text(
        slide, MARGIN, 1.95, 6.0, 3.2,
        "Un cambio **pequeño** causa un salto **grande**.", 50, INK,
        anchor=MSO_ANCHOR.MIDDLE, name="Frase",
    )  # fmt: skip
    cx, cy, cw, ch = 7.7, 1.95, 4.9, 3.2
    pts = _jump_curve(cw, ch)
    builder = slide.shapes.build_freeform(inch(cx + pts[0][0]), inch(cy + pts[0][1]))
    builder.add_line_segments([(inch(cx + px), inch(cy + py)) for px, py in pts[1:]], close=False)
    curve = builder.convert_to_shape()
    curve.name = "Esquema del salto"
    curve.fill.background()
    curve.line.color.rgb = rgb(INK)
    curve.line.width = Pt(5)
    curve.shadow.inherit = False
    _drop_theme_effects(curve)
    add_text(slide, cx, cy + 0.75, 3.2, 0.5, "cambio pequeño", BODY_PT, MUTED, name="Etiqueta 1")
    add_text(
        slide, cx - 0.2, cy + 1.6, 3.4, 0.5, "salto grande", BODY_PT, MUTED,
        align=PP_ALIGN.RIGHT, name="Etiqueta 2",
    )  # fmt: skip
    chip_gap = 0.5
    chip_w = (CONTENT_W - 2 * chip_gap) / 3
    for i, label in enumerate(("clima", "ecosistemas", "mercados")):
        chip = add_shape(
            slide, MSO_SHAPE.ROUNDED_RECTANGLE, MARGIN + i * (chip_w + chip_gap), 5.5,
            chip_w, 0.95, fill=GRID, name=f"Ejemplo {label}",
        )  # fmt: skip
        chip.adjustments[0] = 0.5
        shape_text(chip, label, BODY_PT, INK)
    return slide


def slide_04_model(prs: PresentationType) -> Slide:
    """Model: ball in valleys, deterministic part only."""

    def below(slide: Slide, y: float) -> None:
        add_text(slide, MARGIN, y, 6.0, 0.7, "dx/dt = r + x − x³", FORMULA_PT, INK, name="Fórmula")
        key = add_text(slide, 6.9, y + 0.08, 5.7, 0.6, "", SMALL_PT, INK, name="Leyenda")
        _legend_runs(key)

    return figure_slide(
        prs, 4, "Una bola en un paisaje de valles", FIG_DIR / "s04_landscapes.png",
        "Tres paisajes de potencial para r = 0, −0,2 y −0,385: el valle derecho se aplana.",
        reserve=1.0, below=below,
    )  # fmt: skip


def _legend_runs(box: BaseShape) -> None:
    """Fill the legend: stable glyph in blue, unstable glyph in coral, words in ink."""
    paragraph = box.text_frame.paragraphs[0]
    for text, color in (
        ("● ", PALETTE.stable), ("valle estable    ", INK),
        ("○ ", PALETTE.unstable), ("cima inestable", INK),
    ):  # fmt: skip
        run = paragraph.add_run()
        run.text = text
        _style_run(run, SMALL_PT, color, bold=color != INK)


def slide_05_bifurcation(prs: PresentationType) -> Slide:
    """Equilibria and stability: bifurcation diagram plus the growth rate formula."""

    def below(slide: Slide, y: float) -> None:
        add_text(slide, MARGIN, y, 5.2, 0.7, "λ(x) = 1 − 3x²", FORMULA_PT, INK, name="Fórmula")
        add_text(
            slide, 6.0, y + 0.08, 6.6, 0.6, "estable cuando λ < 0; el borde está en λ = 0",
            SMALL_PT, INK, name="Lectura",
        )  # fmt: skip

    return figure_slide(
        prs, 5, "Al bajar r, un valle desaparece", FIG_DIR / "s05_bifurcation.png",
        "Diagrama de bifurcación: ramas estables (azul) e inestable (coral) con dos bifurcaciones "
        "silla-nodo en r = ±0,385.",
        reserve=0.95, below=below,
    )  # fmt: skip


def slide_06_a1(prs: PresentationType) -> Slide:
    """Animation A1: the valley disappears."""
    slide, _ = video_slide(
        prs, 6, "Así desaparece un valle", "a1_bifurcation",
        "Animación: el paisaje de potencial pierde su valle derecho mientras r baja; la bola cae "
        "al otro valle en la bifurcación silla-nodo.",
        video_h=5.3,
    )  # fmt: skip
    return slide


def slide_07_hysteresis(prs: PresentationType) -> Slide:
    """Hysteresis loop."""

    def below(slide: Slide, y: float) -> None:
        add_text(
            slide, MARGIN, y, CONTENT_W, 0.6,
            "Al subir r de nuevo, el salto ocurre en otro lugar.", BODY_PT, INK, name="Lectura",
        )  # fmt: skip

    return figure_slide(
        prs, 7, "Ida y vuelta no son el mismo camino", FIG_DIR / "s07_hysteresis.png",
        "Diagrama con lazo de histéresis: el salto hacia abajo ocurre en r = −0,385 y el salto "
        "hacia arriba en r = +0,385.",
        reserve=0.8, below=below,
    )  # fmt: skip


def slide_08_noise(prs: PresentationType) -> Slide:
    """Stochastic physics: three-node timeline (native shapes), figure and formula."""
    slide = new_slide(prs, "El ruido es física desde 1905", 8)
    nodes = [("1905", "Einstein"), ("1908", "Langevin"), ("1930", "Uhlenbeck–Ornstein")]
    x_dot, y0, pitch = 0.95, 2.0, 1.3
    spine = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        inch(x_dot),
        inch(y0 + 0.15),
        inch(x_dot),
        inch(y0 + 2 * pitch + 0.15),
    )
    spine.name = "Línea de tiempo"
    spine.line.color.rgb = rgb(MUTED)
    spine.line.width = Pt(2.5)
    _drop_theme_effects(spine)
    for i, (year, who) in enumerate(nodes):
        y = y0 + i * pitch
        add_shape(
            slide, MSO_SHAPE.OVAL, x_dot - 0.15, y, 0.3, 0.3, fill=INK, line=BG, line_pt=3,
            name=f"Nodo {year}",
        )  # fmt: skip
        add_text(slide, 1.4, y - 0.18, 3.2, 0.55, year, 32, INK, bold=True, name=f"Año {year}")
        add_text(slide, 1.4, y + 0.38, 2.9, 0.5, who, SMALL_PT, INK, name=f"Autor {year}")
    fig_x = 4.4
    _, (_, fy, _, fh) = add_picture_fit(
        slide, FIG_DIR / "s08_noise.png", fig_x, 1.75, SLIDE_W - MARGIN - fig_x, 3.7,
        "Relajación hacia x* = 1 sin ruido (izquierda) y con ruido σ = 0,05 (derecha).",
    )  # fmt: skip
    y = fy + fh + 0.3
    add_text(slide, fig_x, y, 4.6, 0.75, "dx = f dt + σ dW", 36, INK, name="Fórmula")
    add_text(
        slide, fig_x + 4.8, y + 0.12, 2.9, 0.6, "determinista + ruido", SMALL_PT, MUTED,
        name="Lectura",
    )  # fmt: skip
    return slide


def slide_09_a2(prs: PresentationType) -> Slide:
    """Animation A2: the noisy ball."""
    slide, _ = video_slide(
        prs, 9, "Con ruido, la bola tiembla más al final", "a2_noisy_ball",
        "Animación: la bola con ruido fluctúa más y más lento a medida que el valle se aplana.",
        video_h=5.3,
    )  # fmt: skip
    return slide


def slide_10_signal(prs: PresentationType) -> Slide:
    """Build the signal slide: variance and AR(1) with two formulas under the figure."""

    def below(slide: Slide, y: float) -> None:
        add_text(slide, MARGIN, y, 5.6, 0.7, "Var = σ² / (2|λ|)", 30, INK, name="Fórmula varianza")
        add_text(
            slide, 6.9, y, 5.6, 0.7, "ρ(Δt) = e^{λΔt}", 30, INK, name="Fórmula autocorrelación"
        )

    return figure_slide(
        prs, 10, "Cerca del borde, todo se vuelve más lento", FIG_DIR / "s10_signal.png",
        "Valle empinado frente a valle plano: series, distribuciones y autocorrelación; el valle "
        "plano fluctúa más y recuerda más tiempo.",
        reserve=0.95, below=below,
    )  # fmt: skip


def slide_11_experiment(prs: PresentationType, kn: dict[str, Any]) -> Slide:
    """Experiment design: ramp versus control."""
    base = kn["baseline"]
    n = int(base["n_runs"])
    sigma = fmt_es(float(base["sigma"]))

    def below(slide: Slide, y: float) -> None:
        add_text(
            slide, MARGIN, y, CONTENT_W, 0.6,
            f"{n} rampas vs {n} controles · σ = {sigma}", BODY_PT, INK, name="Lectura",
        )  # fmt: skip

    return figure_slide(
        prs, 11, "El experimento: rampas contra controles", FIG_DIR / "s11_experiment.png",
        "Una rampa de r de 0 a −0,6 cae hacia t ≈ 1283; el control con r = 0 permanece estable.",
        reserve=0.8, below=below,
    )  # fmt: skip


def slide_12_results(prs: PresentationType, kn: dict[str, Any]) -> Slide:
    """Results: A3 video plus three stat callouts from key_numbers.json."""
    base = kn["baseline"]
    slide, vw = video_slide(
        prs, 12, "Las señales suben antes de la caída", "a3_rolling_window",
        "Animación: ventana móvil sobre una rampa; la varianza y el AR(1) crecen frente al control "
        "hasta el salto.",
        video_h=4.5, x=MARGIN, y=1.75,
    )  # fmt: skip
    stats = [
        (fmt_es(float(base["auc_ar1"])), "AUC del AR(1)"),
        (fmt_es(float(base["auc_var"])), "AUC de la varianza"),
        (fmt_es(float(base["tpr_ar1"])), "TPR del AR(1) con 5 % de falsos positivos"),
    ]
    x = MARGIN + vw + 0.6
    w = SLIDE_W - MARGIN - x
    y = 1.55
    for i, (value, label) in enumerate(stats):
        add_text(slide, x, y, w, 0.95, value, 56, PALETTE.ramp, bold=True, name=f"Cifra {i + 1}")
        add_text(slide, x, y + 0.95, w, 0.8, label, 22, INK, name=f"Etiqueta {i + 1}")
        y += 1.8
    return slide


def slide_13_control(prs: PresentationType) -> Slide:
    """Why a control group."""

    def below(slide: Slide, y: float) -> None:
        add_text(
            slide, MARGIN, y, CONTENT_W, 0.6,
            "El azar también crea tendencias: el control fija el umbral.", BODY_PT, INK,
            name="Lectura",
        )  # fmt: skip

    return figure_slide(
        prs, 13, "Sin control, cualquier tendencia parece señal", FIG_DIR / "s13_control.png",
        "Histogramas del τ de Kendall del AR(1): control (verde) y rampa (violeta) con el umbral "
        "del 5 % de falsos positivos.",
        reserve=0.8, below=below,
    )  # fmt: skip


def slide_14_heatmap(prs: PresentationType, kn: dict[str, Any]) -> Slide:
    """When it fails: AUC heatmap with two takeaways derived from the sweep table."""
    sigmas = sweep_axis(kn, "sigma")
    durations = sweep_axis(kn, "duration")
    sigma_mid = sigmas[1]
    sigma_hi = sigmas[-1]
    short = fmt_es(sweep_cell(kn, sigma_mid, durations[0])["auc_ar1_mean"])
    long_ = fmt_es(sweep_cell(kn, sigma_mid, durations[-1])["auc_ar1_mean"])

    def below(slide: Slide, y: float) -> None:
        add_text(
            slide, MARGIN, y, CONTENT_W, 0.5,
            f"A σ = {fmt_es(sigma_mid)}, el AUC del AR(1) pasa de {short} (rampa corta) "
            f"a {long_} (larga).",
            SMALL_PT, INK, name="Lectura 1",
        )  # fmt: skip
        add_text(
            slide, MARGIN, y + 0.55, CONTENT_W, 0.5,
            f"Con σ = {fmt_es(sigma_hi)} hasta el control cae solo.", SMALL_PT, INK,
            name="Lectura 2",
        )  # fmt: skip

    return figure_slide(
        prs, 14, "Rampas cortas y mucho ruido: señal perdida", FIG_DIR / "s14_heatmap.png",
        "Mapas de calor del AUC para AR(1) y varianza según ruido y duración de la rampa; "
        "las celdas rayadas indican que el control también cae solo.",
        reserve=1.3, below=below,
    )  # fmt: skip


def slide_15_takeaways(prs: PresentationType) -> Slide:
    """Takeaways, honest limitation, repository placeholder and questions."""
    slide = new_slide(prs, "Avisan, pero no dicen cuándo", 15)
    add_text(
        slide, MARGIN, 1.8, 7.3, 3.1,
        [
            "Varianza y AR(1) suben antes de la caída.",
            "Avisan que el borde se acerca, no cuándo.",
            "Rampas cortas o ruido alto: se pierde la señal.",
        ],
        BODY_PT, INK, space_after=18, name="Mensajes",
    )  # fmt: skip
    add_text(
        slide, MARGIN, 4.75, 7.3, 0.9,
        "**Límite:** modelo de juguete, sin datos reales.", SMALL_PT, INK, italic=True,
        name="Límite",
    )  # fmt: skip
    add_text(slide, MARGIN, 5.95, 5.0, 0.7, "¿Preguntas?", 32, INK, bold=True, name="Preguntas")
    qr = add_shape(
        slide, MSO_SHAPE.RECTANGLE, 9.15, 1.8, 3.0, 3.0, fill=None, line=MUTED, line_pt=2,
        dashed=True, name="Marcador de QR",
    )  # fmt: skip
    shape_text(qr, "Repositorio", BODY_PT, INK)
    add_text(
        slide, 8.2, 5.0, 4.9, 0.4, "github.com/<usuario>/tipping-early-warning", 16, MUTED,
        align=PP_ALIGN.CENTER, name="URL del repositorio",
    )  # fmt: skip
    return slide


# --------------------------------------------------------------------------- backups
def backup_01_ou(prs: PresentationType, number: int) -> Slide:
    """Linearisation to Ornstein–Uhlenbeck."""
    slide = new_slide(prs, "Respaldo · De la linealización al OU", number)
    formula_rows(
        slide,
        [
            ("Ecuación", "dx = f(x, r) dt + σ dW"),
            ("Cerca del equilibrio", "x = x* + δ,   f ≈ λδ,   λ = f′(x*) = 1 − 3x*²"),
            ("Linealización (OU)", "dδ = λδ dt + σ dW,   θ = |λ|"),
            ("Varianza estacionaria", "Var = σ² / (2|λ|)"),
            ("Autocorrelación", "ρ(Δt) = e^{λΔt},   AR(1): φ = e^{λΔt}"),
            ("Cerca del borde", "λ → 0:   Var → ∞,   φ → 1"),
        ],
        y0=1.65, size=28, pitch=0.9, label_w=3.4,
    )  # fmt: skip
    return slide


def backup_02_cardano(prs: PresentationType, number: int) -> Slide:
    """Cardano, discriminant and the trigonometric form."""
    slide = new_slide(prs, "Respaldo · Cardano y raíces complejas", number)
    y = formula_rows(
        slide,
        [
            ("Equilibrios", "x³ − x − r = 0"),
            ("Discriminante", "Δ = 4 − 27r² > 0  ⇔  |r| < r_{c} = 2/(3√3)"),
            ("Tres raíces reales", "Cardano pasa por complejos (casus irreducibilis)"),
            ("Forma trigonométrica", "x_{k} = (2/√3) cos[ (1/3) arccos( (3√3/2) r ) − 2πk/3 ]"),
            ("Una raíz real", "|r| ≥ r_{c}: Cardano con raíces cúbicas reales"),
        ],
        y0=1.6, size=26, pitch=0.76, label_w=3.0,
    )  # fmt: skip
    note = add_shape(
        slide, MSO_SHAPE.ROUNDED_RECTANGLE, MARGIN, y + 0.15, CONTENT_W, 1.0, fill=GRID,
        name="Nota x³ + x + r",
    )  # fmt: skip
    note.adjustments[0] = 0.12
    shape_text(
        note, "En cambio x³ + x + r = 0 tiene una sola raíz real (Δ = −4 − 27r² < 0): no hay "
        "bifurcación.", SMALL_PT, INK, align=PP_ALIGN.LEFT, margin=0.3,
    )  # fmt: skip
    return slide


def backup_03_stats(prs: PresentationType, number: int) -> Slide:
    """Kendall tau and AUC in three lines."""
    slide = new_slide(prs, "Respaldo · τ de Kendall y AUC", number)
    add_text(
        slide, MARGIN, 1.9, CONTENT_W, 4.5,
        [
            "**τ de Kendall:** correlación de rangos entre el indicador y el tiempo; "
            "+1 si sube siempre.",
            "**AUC:** probabilidad de que una rampa tenga τ mayor que un control; 0,5 es azar.",
            "**TPR al 5 % FPR:** umbral = percentil 95 de los τ del control.",
        ],
        BODY_PT, INK, space_after=26, name="Definiciones",
    )  # fmt: skip
    return slide


def backup_04_limits(prs: PresentationType, number: int) -> Slide:
    """Sweep details and honest limits."""
    slide = new_slide(prs, "Respaldo · Detalles del barrido y límites", number)
    _, (_, fy, fw, _) = add_picture_fit(
        slide, FIG_DIR / "b04_tipped.png", MARGIN, 2.0, 7.7, 4.6,
        "Mapas de la fracción de corridas que caen solas: control (izquierda) y rampa antes de "
        "tiempo (derecha), según ruido y duración.",
    )  # fmt: skip
    x = MARGIN + fw + 0.4
    add_text(
        slide, x, fy, SLIDE_W - MARGIN - x, 4.6,
        [
            "La ventana depende de la duración de la rampa.",
            f"Con σ = {fmt_es(sweep_axis(load_key_numbers(), 'sigma')[-1])} el control cae solo.",
            "Con ruido alto, muchas rampas caen antes del análisis (sesgo de supervivencia).",
        ],
        22, INK, space_after=16, name="Límites",
    )  # fmt: skip
    return slide


def backup_05_static(prs: PresentationType, number: int) -> Slide:
    """Build the static results figure (plan B if the A3 video fails)."""
    return figure_slide(
        prs, number, "Respaldo · Resultados estáticos", FIG_DIR / "s12_results.png",
        "Varianza móvil y AR(1) móvil de las rampas (violeta) frente al control (verde), con "
        "percentiles 10 a 90 %.",
    )  # fmt: skip


def backup_06_noise(prs: PresentationType, number: int) -> Slide:
    """Increasing-noise confound (only built when its figure exists)."""
    return figure_slide(
        prs,
        number,
        "Respaldo · Solo el AR(1) distingue ruido y borde",
        FIG_DIR / "b05_noise_confound.png",
        "Con r fijo y ruido creciente la varianza sube (AUC 1,00) pero el AR(1) no (0,52); "
        "al acercarse a la bifurcación suben ambos.",
    )  # fmt: skip


# --------------------------------------------------------------------------- build
def hide(slide: Slide) -> None:
    """Hide a slide in slide-show mode."""
    slide._element.set("show", "0")


def export_pdf(pptx_path: Path) -> Path | None:
    """Convert to PDF with LibreOffice if available; returns the PDF path or ``None``."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        print("LibreOffice not found: skipping PDF export")
        return None
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pptx_path.parent),
             str(pptx_path)],
            check=True, timeout=240, capture_output=True,
        )  # fmt: skip
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"PDF export failed: {exc}")
        return None
    pdf = pptx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def build_deck(*, reveal_backups: bool = False) -> tuple[Path, list[str]]:
    """Build the deck; returns the PPTX path and the notes keys actually used.

    ``reveal_backups`` leaves the backup slides visible and writes ``*_qa.pptx`` instead,
    so a PDF export shows every slide for visual checks.
    """
    kn = load_key_numbers()
    notes = load_notes()
    prs = new_presentation()
    keyed: list[tuple[str, Slide]] = []

    main: list[tuple[str, Callable[[], Slide]]] = [
        ("1", lambda: slide_01_hook(prs)),
        ("2", lambda: slide_02_idea(prs)),
        ("3", lambda: slide_03_tipping(prs)),
        ("4", lambda: slide_04_model(prs)),
        ("5", lambda: slide_05_bifurcation(prs)),
        ("6", lambda: slide_06_a1(prs)),
        ("7", lambda: slide_07_hysteresis(prs)),
        ("8", lambda: slide_08_noise(prs)),
        ("9", lambda: slide_09_a2(prs)),
        ("10", lambda: slide_10_signal(prs)),
        ("11", lambda: slide_11_experiment(prs, kn)),
        ("12", lambda: slide_12_results(prs, kn)),
        ("13", lambda: slide_13_control(prs)),
        ("14", lambda: slide_14_heatmap(prs, kn)),
        ("15", lambda: slide_15_takeaways(prs)),
    ]
    for key, make in main:
        keyed.append((key, make()))

    backups: list[tuple[str, Callable[[PresentationType, int], Slide]]] = [
        ("B1", backup_01_ou),
        ("B2", backup_02_cardano),
        ("B3", backup_03_stats),
        ("B4", backup_04_limits),
        ("B5", backup_05_static),
    ]
    if (FIG_DIR / "b05_noise_confound.png").exists():
        backups.append(("B6", backup_06_noise))
    else:
        print("b05_noise_confound.png missing: backup B6 skipped")
    for key, make_backup in backups:
        slide = make_backup(prs, len(keyed) + 1)
        if not reveal_backups:
            hide(slide)
        keyed.append((key, slide))

    used: list[str] = []
    for key, slide in keyed:
        if key in notes:
            slide.notes_slide.notes_text_frame.text = notes[key]
            used.append(key)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{OUT_NAME}{'_qa' if reveal_backups else ''}.pptx"
    prs.save(str(out))
    return out, used


def main() -> None:
    """Build the PPTX and the PDF export and print a short summary.

    Pass ``--qa-all`` to build the visual-check variant with the backups unhidden.
    """
    out, used = build_deck(reveal_backups="--qa-all" in sys.argv[1:])
    print(f"written {out} ({out.stat().st_size / 1e6:.1f} MB); notes for: {', '.join(used) or '-'}")
    pdf = export_pdf(out)
    if pdf is not None:
        print(f"written {pdf} ({pdf.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
