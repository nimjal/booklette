"""booklette - turn a page-by-page PDF into a foldable booklet.

Quick start::

    from booklette import BookletOptions, Duplex, create_booklet

    create_booklet("report.pdf", "report-booklet.pdf", BookletOptions(margin_mm=8))

Each sheet of the output holds two portrait pages side by side, ordered so that
printing the file duplex and folding the stack in half produces a half-size
booklet that reads in the right order.
"""

from __future__ import annotations

from .builder import (
    BookletError,
    BookletOptions,
    BookletResult,
    create_booklet,
    default_output_path,
)
from .filler import DEFAULT_TITLE, Filler
from .imposition import (
    BACK_COVER_PAGE,
    BLANK_PAGE,
    PAGES_PER_SHEET,
    Duplex,
    Sheet,
    SheetOrder,
    SheetSide,
    format_plan,
    impose,
    is_padding,
)
from .layout import Placement, Rect, SheetLayout, build_sheet_layout, place
from .paper import PAPER_SIZES_MM, mm_to_points, parse_paper, points_to_mm

__version__ = "0.1.0"

__all__ = [
    "BACK_COVER_PAGE",
    "BLANK_PAGE",
    "DEFAULT_TITLE",
    "PAGES_PER_SHEET",
    "PAPER_SIZES_MM",
    "BookletError",
    "BookletOptions",
    "BookletResult",
    "Duplex",
    "Filler",
    "Placement",
    "Rect",
    "Sheet",
    "SheetLayout",
    "SheetOrder",
    "SheetSide",
    "__version__",
    "build_sheet_layout",
    "create_booklet",
    "default_output_path",
    "format_plan",
    "impose",
    "is_padding",
    "mm_to_points",
    "parse_paper",
    "place",
    "points_to_mm",
]
