"""Export the spoken parts of the talk script as speaker notes.

Parses ``deck/guion.md`` and writes ``deck/notes.json``, a mapping from slide key
(``"1"`` to ``"15"`` for the slides, ``"B1"`` to ``"B6"`` for the hidden backups) to the text of
the ``**Decir:**`` block followed by the ``**Transición:**`` block of that section. The deck
build reads the JSON file; nothing in it is typed by hand.

Run with ``uv run python deck/export_notes.py`` (add ``--stats`` to print word counts and the
estimated speaking time of the main slides).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_GUION = HERE / "guion.md"
DEFAULT_OUT = HERE / "notes.json"

SPOKEN_LABELS: tuple[str, ...] = ("Decir", "Transición")
WORDS_PER_MINUTE = 145.0

_SECTION_RE = re.compile(r"^## (?:Slide (?P<slide>\d+)|Respaldo (?P<backup>B\d+)) —")
_LABEL_RE = re.compile(r"^\*\*(?P<label>[^*:]+):\*\*[ \t]*(?P<rest>.*)$")
_CUE_RE = re.compile(r"\[[^\]]*\]")


def _is_boundary(line: str) -> bool:
    """Return whether ``line`` ends the current labelled block."""
    return line.startswith("#") or line.strip() == "---" or _LABEL_RE.match(line) is not None


def _clean(text: str) -> str:
    """Strip Markdown bold markers and surrounding blank space from a block."""
    return re.sub(r"\n{3,}", "\n\n", text.replace("**", "")).strip()


def split_sections(text: str) -> dict[str, list[str]]:
    """Split the script into per-slide and per-backup line lists.

    Parameters
    ----------
    text : str
        Full Markdown text of the script.

    Returns
    -------
    dict of str to list of str
        Section key (``"1"`` ... ``"15"``, ``"B1"`` ... ``"B6"``) to the lines under its heading,
        in file order. Sections end at the next level-2 heading.
    """
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        match = _SECTION_RE.match(line)
        if match is not None:
            key = match.group("slide") or match.group("backup")
            current = sections.setdefault(key, [])
        elif line.startswith("## "):
            current = None
        elif current is not None:
            current.append(line)
    return sections


def extract_blocks(lines: list[str], labels: tuple[str, ...] = SPOKEN_LABELS) -> dict[str, str]:
    """Collect the labelled blocks of one section.

    Parameters
    ----------
    lines : list of str
        Lines of the section, as returned by :func:`split_sections`.
    labels : tuple of str, optional
        Labels to keep (without the surrounding ``**`` and colon).

    Returns
    -------
    dict of str to str
        Label to the cleaned text of its block. Labels absent from the section are omitted.
    """
    blocks: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        label_match = _LABEL_RE.match(line)
        if label_match is not None:
            label = label_match.group("label").strip()
            if label in labels:
                current = blocks.setdefault(label, [])
                rest = label_match.group("rest")
                if rest:
                    current.append(rest)
            else:
                current = None
        elif _is_boundary(line):
            current = None
        elif current is not None:
            current.append(line)
    return {label: _clean("\n".join(body)) for label, body in blocks.items()}


def parse_guion(text: str) -> dict[str, str]:
    """Build the notes mapping from the script text.

    Parameters
    ----------
    text : str
        Full Markdown text of the script.

    Returns
    -------
    dict of str to str
        Section key to the ``Decir`` block followed by the ``Transición`` block, separated by a
        blank line. Sections without any spoken block are omitted.
    """
    notes: dict[str, str] = {}
    for key, lines in split_sections(text).items():
        blocks = extract_blocks(lines)
        parts = [blocks[label] for label in SPOKEN_LABELS if blocks.get(label)]
        if parts:
            notes[key] = "\n\n".join(parts)
    return dict(sorted(notes.items(), key=lambda item: _sort_key(item[0])))


def _sort_key(key: str) -> tuple[int, int]:
    """Order slides numerically first, then backups."""
    if key.startswith("B"):
        return (1, int(key[1:]))
    return (0, int(key))


def spoken_words(text: str) -> int:
    """Count the words that are actually said, ignoring ``[...]`` stage directions.

    Parameters
    ----------
    text : str
        Notes text of one section.

    Returns
    -------
    int
        Number of whitespace-separated words outside square brackets.
    """
    return len(_CUE_RE.sub(" ", text).split())


def format_stats(notes: dict[str, str]) -> str:
    """Return a table of spoken words per main slide and the estimated total time.

    Parameters
    ----------
    notes : dict of str to str
        Mapping produced by :func:`parse_guion`.

    Returns
    -------
    str
        Plain-text report.
    """
    rows: list[str] = []
    total = 0
    for key, text in notes.items():
        if key.startswith("B"):
            continue
        words = spoken_words(text)
        total += words
        rows.append(f"slide {key:>2}: {words:4d} words  ({words / WORDS_PER_MINUTE * 60:5.1f} s)")
    minutes = total / WORDS_PER_MINUTE
    rows.append(f"total   : {total:4d} words  ({minutes:.1f} min at {WORDS_PER_MINUTE:.0f} wpm)")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> None:
    """Parse the script, write the JSON notes file and report what was exported.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--guion", type=Path, default=DEFAULT_GUION, help="input Markdown script")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSON file")
    parser.add_argument("--stats", action="store_true", help="print word counts and timing")
    args = parser.parse_args(argv)

    notes = parse_guion(args.guion.read_text(encoding="utf-8"))
    args.out.write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} with {len(notes)} entries: {', '.join(notes)}")
    if args.stats:
        print(format_stats(notes))


if __name__ == "__main__":
    main()
