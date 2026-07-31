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
from .imposition import (
    BLANK_PAGE,
    PAGES_PER_SHEET,
    Duplex,
    Sheet,
    SheetOrder,
    SheetSide,
    format_plan,
    impose,
)
from .layout import Placement, Rect, SheetLayout, build_sheet_layout, place
from .paper import PAPER_SIZES_MM, mm_to_points, parse_paper, points_to_mm

__version__ = "0.1.0"

__all__ = [
    "BLANK_PAGE",
    "PAGES_PER_SHEET",
    "PAPER_SIZES_MM",
    "BookletError",
    "BookletOptions",
    "BookletResult",
    "Duplex",
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
    "mm_to_points",
    "parse_paper",
    "place",
    "points_to_mm",
]
