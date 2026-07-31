"""Use booklette as a library.

    python examples/basic_usage.py

Creates a 12 page sample document, then imposes it three different ways so you
can compare the results in a PDF viewer.
"""

from __future__ import annotations

from pathlib import Path

from make_sample_pdf import make_numbered_pdf

from booklette import BookletOptions, Duplex, SheetOrder, create_booklet

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    source = make_numbered_pdf(OUTPUT_DIR / "sample.pdf", page_count=12)
    print(f"Sample document: {source}")

    # 1. The defaults: A4, long-edge duplex, sheets emitted last-first for a
    #    printer that stacks its output face up.
    _convert(source, "booklet-default.pdf", BookletOptions())

    # 2. A comfortable reading copy: room for the staple and for fingers.
    _convert(
        source,
        "booklet-with-margins.pdf",
        BookletOptions(margin_mm=8, gutter_mm=5),
    )

    # 3. A thick document folded in groups of 8 pages (2 sheets per group),
    #    printed on a face-down printer that flips on the short edge.
    _convert(
        source,
        "booklet-signatures.pdf",
        BookletOptions(
            signature_size=8,
            duplex=Duplex.SHORT_EDGE,
            order=SheetOrder.NORMAL,
            margin_mm=6,
        ),
    )


def _convert(source: Path, name: str, options: BookletOptions) -> None:
    """Run one conversion and print a short summary of the result."""
    result = create_booklet(source, OUTPUT_DIR / name, options)
    width, height = result.sheet_size_mm
    print(
        f"{name}: {result.source_pages} pages -> {result.sheets} sheets "
        f"({result.output_pages} sides) on {width:g}x{height:g} mm, "
        f"{result.blank_pages} blank(s)"
    )


if __name__ == "__main__":
    main()
