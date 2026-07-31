"""Booklet page ordering ("imposition").

This module is deliberately free of any PDF library: it only answers the
question *"which source page goes where?"*. That makes the tricky part of the
problem easy to read, easy to test, and easy to reuse.

Saddle-stitch booklets
----------------------
Take four sheets of paper, stack them, fold the stack in half and staple the
fold. You get a 16 page booklet. Each sheet carries four pages: two on the
front, two on the back, and they are *not* consecutive::

    sheet 1 front:  [ 16 |  1 ]      sheet 1 back:  [  2 | 15 ]
    sheet 2 front:  [ 14 |  3 ]      sheet 2 back:  [  4 | 13 ]
    sheet 3 front:  [ 12 |  5 ]      sheet 3 back:  [  6 | 11 ]
    sheet 4 front:  [ 10 |  7 ]      sheet 4 back:  [  8 |  9 ]

The pattern for a booklet of ``n`` pages, sheet ``i`` counted from 0:

===========  ==================  ==================
sheet side   left half           right half
===========  ==================  ==================
front        ``n - 2i``          ``2i + 1``
back         ``2i + 2``          ``n - 2i - 1``
===========  ==================  ==================

Because every sheet carries four pages, the page count is padded with blanks up
to a multiple of four.

Signatures
----------
A single fold stops being practical past roughly ten sheets - the inner pages
stick out and the fold bulges. Printers solve this by splitting the book into
*signatures*: several small booklets that are folded separately and then bound
together in order. ``signature_size`` controls that split; ``0`` keeps the whole
document in one signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: Page number used for a padding page that should be left empty.
BLANK_PAGE = 0

#: Every sheet of paper carries four booklet pages (two per side).
PAGES_PER_SHEET = 4


class Duplex(str, Enum):
    """How the printer turns the paper over between the two sides.

    The imposed sheets are landscape, but the paper is fed portrait, so the two
    duplex modes do *not* behave the way the names suggest:

    * :attr:`LONG_EDGE` - the flip axis runs along the long edge of the paper,
      which is perpendicular to the fold of the booklet. The back side must be
      rotated by 180 degrees, otherwise every second page comes out upside down
      and paired with the wrong neighbour. This is the default because it is
      what most printer drivers do by default.
    * :attr:`SHORT_EDGE` - the flip axis matches the booklet fold, so the back
      side is placed exactly like the front side, with no extra rotation.

    If your first test print comes out with the odd pages upside down, you are
    on the wrong setting: switch this option (or switch the printer dialog).
    """

    LONG_EDGE = "long"
    SHORT_EDGE = "short"

    @property
    def rotates_back_side(self) -> bool:
        """True when the back of each sheet must be rotated by 180 degrees."""
        return self is Duplex.LONG_EDGE


class SheetOrder(str, Enum):
    """The order in which finished sheets are handed to the printer.

    * :attr:`REVERSE` - emit the last sheet first. Use this for printers that
      stack pages face up, so the pile grows "bottom to top" and the last page
      printed ends up on top. Reversing the order makes the finished pile come
      out in reading order, ready to fold.
    * :attr:`NORMAL` - emit sheet 1 first, for printers that stack face down.
    """

    NORMAL = "normal"
    REVERSE = "reverse"


@dataclass(frozen=True)
class SheetSide:
    """One printed side of a sheet: two booklet pages, side by side.

    ``left`` and ``right`` are 1-based page numbers of the *source* document, or
    :data:`BLANK_PAGE` for padding. ``rotated`` means the whole side (both
    halves together) is turned 180 degrees to survive long-edge duplex.
    """

    left: int
    right: int
    is_back: bool = False
    rotated: bool = False

    @property
    def pages(self) -> tuple[int, int]:
        """The two page numbers as a ``(left, right)`` tuple."""
        return (self.left, self.right)


@dataclass(frozen=True)
class Sheet:
    """A single sheet of paper: a front side and a back side."""

    front: SheetSide
    back: SheetSide
    #: 0-based index of the signature (folded group) this sheet belongs to.
    signature: int = 0

    @property
    def sides(self) -> tuple[SheetSide, SheetSide]:
        """Both sides in printing order: front first, then back."""
        return (self.front, self.back)


def pad_to_multiple_of_four(pages: list[int]) -> list[int]:
    """Append :data:`BLANK_PAGE` entries until the length is a multiple of four.

    >>> pad_to_multiple_of_four([1, 2, 3, 4, 5])
    [1, 2, 3, 4, 5, 0, 0, 0]
    """
    missing = -len(pages) % PAGES_PER_SHEET
    return pages + [BLANK_PAGE] * missing


def split_into_signatures(pages: list[int], signature_size: int) -> list[list[int]]:
    """Split ``pages`` into folded groups, each padded to a multiple of four.

    ``signature_size`` of ``0`` (or anything larger than the document) keeps
    everything in a single signature.

    >>> split_into_signatures([1, 2, 3, 4, 5, 6], 4)
    [[1, 2, 3, 4], [5, 6, 0, 0]]

    :raises ValueError: if ``signature_size`` is not a positive multiple of four.
    """
    if signature_size < 0:
        raise ValueError("signature_size cannot be negative")
    if signature_size == 0 or signature_size >= len(pages):
        return [pad_to_multiple_of_four(pages)]
    if signature_size % PAGES_PER_SHEET != 0:
        raise ValueError(f"signature_size must be a multiple of {PAGES_PER_SHEET}")

    chunks = [
        pages[start : start + signature_size] for start in range(0, len(pages), signature_size)
    ]
    # Only the last chunk can be short, and it is padded like any other booklet.
    return [pad_to_multiple_of_four(chunk) for chunk in chunks]


def impose_signature(
    pages: list[int],
    *,
    signature: int = 0,
    duplex: Duplex = Duplex.LONG_EDGE,
    right_to_left: bool = False,
) -> list[Sheet]:
    """Turn one padded signature into sheets, following the table in the module docstring.

    ``pages`` must already be padded to a multiple of four - use
    :func:`split_into_signatures` for that.
    """
    if len(pages) % PAGES_PER_SHEET != 0:
        raise ValueError("A signature must contain a multiple of four pages")

    sheets: list[Sheet] = []
    total = len(pages)
    for index in range(total // PAGES_PER_SHEET):
        # Note the -1 offsets: `pages` is a 0-based list, the table is 1-based.
        front = _side(
            left=pages[total - 1 - 2 * index],
            right=pages[2 * index],
            is_back=False,
            rotated=False,
            right_to_left=right_to_left,
        )
        back = _side(
            left=pages[2 * index + 1],
            right=pages[total - 2 - 2 * index],
            is_back=True,
            rotated=duplex.rotates_back_side,
            right_to_left=right_to_left,
        )
        sheets.append(Sheet(front=front, back=back, signature=signature))
    return sheets


def _side(*, left: int, right: int, is_back: bool, rotated: bool, right_to_left: bool) -> SheetSide:
    """Build a :class:`SheetSide`, mirroring it for right-to-left booklets.

    In a right-to-left book (Arabic, Hebrew, Japanese, ...) the spine is on the
    right, so page 1 is the *left* half of the sheet instead of the right one.
    Everything else about the imposition is unchanged.
    """
    if right_to_left:
        left, right = right, left
    return SheetSide(left=left, right=right, is_back=is_back, rotated=rotated)


def impose(
    page_count: int,
    *,
    signature_size: int = 0,
    duplex: Duplex = Duplex.LONG_EDGE,
    order: SheetOrder = SheetOrder.REVERSE,
    right_to_left: bool = False,
) -> list[Sheet]:
    """Plan a whole booklet.

    :param page_count: number of pages in the source document.
    :param signature_size: pages per folded group, or ``0`` for a single fold.
    :param duplex: how the printer flips the paper - see :class:`Duplex`.
    :param order: sheet output order - see :class:`SheetOrder`.
    :param right_to_left: mirror the layout for right-to-left reading.
    :returns: the sheets to print, already in output order.

    >>> [sheet.front.pages for sheet in impose(8, order=SheetOrder.NORMAL)]
    [(8, 1), (6, 3)]
    """
    if page_count < 1:
        raise ValueError("A booklet needs at least one page")

    signatures = split_into_signatures(list(range(1, page_count + 1)), signature_size)

    sheets: list[Sheet] = []
    for number, signature_pages in enumerate(signatures):
        sheets.extend(
            impose_signature(
                signature_pages,
                signature=number,
                duplex=duplex,
                right_to_left=right_to_left,
            )
        )

    if order is SheetOrder.REVERSE:
        # Reverse whole sheets, never the two sides of one sheet: the printer
        # decides which side is printed first, we only decide the sheet order.
        sheets.reverse()
    return sheets


def count_blank_pages(sheets: list[Sheet]) -> int:
    """Count the padding pages added to fill the last sheet(s)."""
    return sum(
        1 for sheet in sheets for side in sheet.sides for page in side.pages if page == BLANK_PAGE
    )


def format_plan(sheets: list[Sheet]) -> str:
    """Render a human-readable imposition table, used by ``--dry-run``.

    Sheets are numbered in the order they are written to the file, which with
    :attr:`SheetOrder.REVERSE` is the opposite of the order they are folded in.

    >>> print(format_plan(impose(4, order=SheetOrder.NORMAL)))
    sheet 1/1  signature 1  front [  4 |  1 ]  back  [  2 |  3 ] rotated 180
    """
    lines = []
    total = len(sheets)
    for index, sheet in enumerate(sheets, start=1):
        parts = [f"sheet {index}/{total}", f"signature {sheet.signature + 1}"]
        for side in sheet.sides:
            name = "back " if side.is_back else "front"
            left = "  -" if side.left == BLANK_PAGE else f"{side.left:3d}"
            right = "  -" if side.right == BLANK_PAGE else f"{side.right:3d}"
            parts.append(f"{name} [{left} |{right} ]{' rotated 180' if side.rotated else ''}")
        lines.append("  ".join(parts))
    return "\n".join(lines)
