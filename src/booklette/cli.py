"""Command line interface for booklette."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .builder import BookletError, BookletOptions, create_booklet, default_output_path
from .imposition import Duplex, SheetOrder, format_plan, impose
from .paper import PAPER_SIZES_MM

EPILOG = f"""\
examples:
  booklette report.pdf
  booklette report.pdf -o handout.pdf --margin 8 --gutter 4
  booklette novel.pdf --signature 16 --duplex short --order normal
  booklette report.pdf --dry-run

known paper sizes: {", ".join(sorted(PAPER_SIZES_MM))} (or a custom "WIDTHxHEIGHT" in mm)

printing:
  Print the result on the chosen paper at 100% scale ("actual size", no
  "fit to page"), duplex, then fold the stack in half and staple the fold.
  If the back sides come out upside down, switch --duplex.
  If the pages come out in the wrong order, switch --order.
"""


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (kept separate so tests can inspect it)."""
    parser = argparse.ArgumentParser(
        prog="booklette",
        description=(
            "Impose a page-by-page PDF onto folded sheets: two portrait pages per "
            "sheet side, ordered so that printing duplex and folding the stack in "
            "half gives a half-size booklet."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="the PDF to convert")
    parser.add_argument(
        "-o",
        "--output",
        help="where to write the booklet (default: <input>-booklet.pdf)",
    )
    parser.add_argument(
        "-p",
        "--paper",
        default="a4",
        help='paper size to print on, e.g. "a4", "letter" or "200x250" (default: a4)',
    )
    parser.add_argument(
        "-d",
        "--duplex",
        type=Duplex,
        # Duplex is a str enum, so the parsed value compares equal to its
        # string form - which keeps the --help output readable: {long,short}.
        choices=[mode.value for mode in Duplex],
        default=Duplex.LONG_EDGE,
        help=(
            "how the printer flips the paper between sides; long-edge flipping "
            "needs the back of each sheet rotated by 180 degrees (default: long)"
        ),
    )
    parser.add_argument(
        "--order",
        type=SheetOrder,
        choices=[order.value for order in SheetOrder],
        default=SheetOrder.REVERSE,
        help=(
            "sheet output order: 'reverse' for printers that stack face up and "
            "fill the tray bottom to top, 'normal' for face-down stacking "
            "(default: reverse)"
        ),
    )
    parser.add_argument(
        "-s",
        "--signature",
        type=int,
        default=0,
        metavar="PAGES",
        help=(
            "fold the book in groups of PAGES pages (a multiple of 4, e.g. 16) "
            "instead of one thick fold; 0 folds everything at once (default: 0)"
        ),
    )
    parser.add_argument(
        "-m",
        "--margin",
        type=float,
        default=0.0,
        metavar="MM",
        help="whitespace at the outer edges of the sheet, in mm (default: 0)",
    )
    parser.add_argument(
        "-g",
        "--gutter",
        type=float,
        default=0.0,
        metavar="MM",
        help="extra whitespace either side of the fold, in mm (default: 0)",
    )
    parser.add_argument(
        "--rtl",
        action="store_true",
        help="right-to-left booklet: the spine ends up on the right",
    )
    parser.add_argument("--password", help="password for an encrypted input PDF")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print the imposition plan without writing a file",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    options = BookletOptions(
        paper=args.paper,
        duplex=args.duplex,
        order=args.order,
        signature_size=args.signature,
        margin_mm=args.margin,
        gutter_mm=args.gutter,
        right_to_left=args.rtl,
        password=args.password,
    )

    try:
        if args.dry_run:
            return _dry_run(args.input, options)

        output = default_output_path(args.input, args.output)
        result = create_booklet(args.input, output, options)
    except (BookletError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not args.quiet:
        width, height = result.sheet_size_mm
        print(f"Wrote {output}")
        print(
            f"  {result.source_pages} pages -> {result.sheets} sheets "
            f"({result.output_pages} sides) of {width:g}x{height:g} mm"
        )
        if result.blank_pages:
            print(f"  {result.blank_pages} blank page(s) added as padding")
        print(
            f"  print duplex (flip on {options.duplex.value} edge) at 100% scale, "
            "then fold and staple"
        )
    return 0


def _dry_run(source: str, options: BookletOptions) -> int:
    """Print the imposition plan for ``source`` without writing anything."""
    from pypdf import PdfReader  # imported lazily so --help stays fast

    reader = PdfReader(source)
    sheets = impose(
        len(reader.pages),
        signature_size=options.signature_size,
        duplex=options.duplex,
        order=options.order,
        right_to_left=options.right_to_left,
    )
    print(format_plan(sheets))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via __main__.py
    raise SystemExit(main())
