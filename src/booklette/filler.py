"""What goes on the padding pages at the back of the booklet.

A folded sheet always carries four pages, so a booklet's page count is a
multiple of four: a 14 page document is printed as 16 and the last two pages are
padding. Rather than hand out empty paper, booklette rules those pages as note
paper - a heading and a set of lines - and leaves only the very last one alone,
because that page is the back cover of the finished booklet.

Like :mod:`booklette.imposition` and :mod:`booklette.layout`, this module has no
PDF library behind it. It produces a *content stream*: the small language of
drawing operators a PDF page is made of, as a plain string, which
:mod:`booklette.builder` attaches to a page. The operators used here are::

    q ... Q     save and restore the graphics state
    RG / rg     stroke and fill colour, as red green blue
    w           line width
    m / l / S   move to, line to, stroke the path
    BT ... ET   a text object
    Tf / Td / Tj    choose a font, move to a baseline, show a string

Everything is measured in the coordinate space of the *source page*, because a
filler page is built at the size of the document's first page and then scaled
into its half of the sheet exactly like a real page. A 9 mm line spacing on an
A4 page therefore prints at about 6.4 mm once that page has been shrunk onto
half of an A4 sheet - the same shrinking the rest of the document goes through.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .paper import mm_to_points

#: Heading printed at the top of a notes page.
DEFAULT_TITLE = "Notes:"

#: Resource name of the font the heading is drawn with. :mod:`booklette.builder`
#: registers a Helvetica under this name on every filler page it makes.
FONT_NAME = "BkltNotes"

#: Whitespace kept around the ruled area, in millimetres of the source page.
MARGIN_MM = 15.0

#: Distance between two ruled lines, in millimetres of the source page.
LINE_SPACING_MM = 9.0

#: Size of the heading, in points of the source page.
TITLE_SIZE_PT = 14.0

#: Fraction of the page the margin is capped at, so that a small page (an A7
#: flyer, say) keeps a usable area instead of being all margin.
_MAX_MARGIN_FRACTION = 0.12


class Filler(str, Enum):
    """What to draw on the padding pages at the back of the booklet.

    * :attr:`NOTES` - a "Notes:" heading and ruled lines. The default.
    * :attr:`NOTES_PLAIN` - the heading on its own, for blank note space.
    * :attr:`LINES` - ruled lines without a heading.
    * :attr:`BLANK` - nothing at all, the way padding pages used to be.

    The back cover - the last page of the booklet - is left empty whichever
    of these is chosen, unless ``fill_back_cover`` says otherwise.
    """

    NOTES = "notes"
    NOTES_PLAIN = "notes-plain"
    LINES = "lines"
    BLANK = "blank"

    @property
    def draws_title(self) -> bool:
        """True when this filler prints a heading."""
        return self in (Filler.NOTES, Filler.NOTES_PLAIN)

    @property
    def draws_lines(self) -> bool:
        """True when this filler prints ruled lines."""
        return self in (Filler.NOTES, Filler.LINES)

    @property
    def draws_anything(self) -> bool:
        """True unless this filler leaves the page empty."""
        return self is not Filler.BLANK


@dataclass(frozen=True)
class NotesLayout:
    """Where the heading and the ruled lines sit on a filler page, in points.

    ``title_baseline`` is ``None`` when the filler prints no heading, or when
    the page is too small for one; ``line_ys`` is empty when it prints no lines.
    """

    left: float
    right: float
    title_baseline: float | None
    line_ys: tuple[float, ...]

    @property
    def is_empty(self) -> bool:
        """True when there is nothing to draw."""
        return self.title_baseline is None and not self.line_ys


def plan_notes(
    width: float,
    height: float,
    filler: Filler,
    *,
    margin_mm: float = MARGIN_MM,
    line_spacing_mm: float = LINE_SPACING_MM,
) -> NotesLayout:
    """Work out where the heading and the lines go on a page of ``width`` x ``height``.

    Both sizes are in points. The heading sits just below the top margin and the
    lines fill what is left, one every ``line_spacing_mm``.

    >>> layout = plan_notes(595.0, 842.0, Filler.NOTES)
    >>> round(layout.left, 1), round(layout.right, 1)
    (42.5, 552.5)
    >>> plan_notes(595.0, 842.0, Filler.BLANK).is_empty
    True
    """
    if line_spacing_mm <= 0:
        raise ValueError("line spacing must be positive")

    empty = NotesLayout(left=0.0, right=0.0, title_baseline=None, line_ys=())
    if not filler.draws_anything or width <= 0 or height <= 0:
        return empty

    # Cap the margin on small pages, so they keep a usable area.
    margin = min(
        mm_to_points(margin_mm),
        width * _MAX_MARGIN_FRACTION,
        height * _MAX_MARGIN_FRACTION,
    )
    left, right = margin, width - margin
    bottom, top = margin, height - margin
    if right <= left or top <= bottom:
        return empty

    title_baseline = None
    first_line = top
    if filler.draws_title and top - TITLE_SIZE_PT >= bottom:
        title_baseline = top - TITLE_SIZE_PT
        first_line = title_baseline

    spacing = mm_to_points(line_spacing_mm)
    line_ys = _line_positions(first_line - spacing, bottom, spacing) if filler.draws_lines else ()
    return NotesLayout(left=left, right=right, title_baseline=title_baseline, line_ys=line_ys)


def _line_positions(top: float, bottom: float, spacing: float) -> tuple[float, ...]:
    """Ruled line heights from ``top`` downwards, stopping at ``bottom``.

    >>> _line_positions(100.0, 40.0, 25.0)
    (100.0, 75.0, 50.0)
    """
    positions = []
    y = top
    while y >= bottom:
        positions.append(y)
        y -= spacing
    return tuple(positions)


def content_stream(
    width: float,
    height: float,
    filler: Filler,
    *,
    title: str = DEFAULT_TITLE,
    margin_mm: float = MARGIN_MM,
    line_spacing_mm: float = LINE_SPACING_MM,
) -> str:
    """Draw one filler page, as PDF operators. Empty string when nothing is drawn.

    >>> stream = content_stream(595.0, 842.0, Filler.NOTES_PLAIN)
    >>> "(Notes:) Tj" in stream
    True
    >>> content_stream(595.0, 842.0, Filler.BLANK)
    ''
    """
    layout = plan_notes(width, height, filler, margin_mm=margin_mm, line_spacing_mm=line_spacing_mm)
    if layout.is_empty:
        return ""

    parts: list[str] = []
    if layout.line_ys:
        parts.append("q\n0.72 0.72 0.72 RG\n0.6 w")
        parts.extend(
            f"{_num(layout.left)} {_num(y)} m {_num(layout.right)} {_num(y)} l S"
            for y in layout.line_ys
        )
        parts.append("Q")
    if layout.title_baseline is not None and title:
        parts.append(
            "BT\n"
            f"/{FONT_NAME} {_num(TITLE_SIZE_PT)} Tf\n"
            "0.25 0.25 0.25 rg\n"
            f"{_num(layout.left)} {_num(layout.title_baseline)} Td\n"
            f"({_pdf_string(title)}) Tj\n"
            "ET"
        )
    # A heading-only filler with an empty title leaves nothing to draw.
    return "\n".join(parts) + "\n" if parts else ""


def _num(value: float) -> str:
    """Format a coordinate for a content stream, without pointless decimals.

    >>> _num(42.5), _num(100.0), _num(0.0)
    ('42.5', '100', '0')
    """
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")


def _pdf_string(text: str) -> str:
    r"""Escape ``text`` for use inside a PDF literal string.

    The heading is drawn with Helvetica, whose built-in encoding covers Latin-1,
    so anything outside that is replaced rather than silently mangled.

    >>> _pdf_string("Notes (draft): a\\b")
    'Notes \\(draft\\): a\\\\b'
    """
    safe = text.encode("latin-1", "replace").decode("latin-1")
    safe = "".join(character if character >= " " else " " for character in safe)
    for old, new in (("\\", r"\\"), ("(", r"\("), (")", r"\)")):
        safe = safe.replace(old, new)
    return safe
