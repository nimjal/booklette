"""Inspect the page ordering without touching a PDF at all.

    python examples/print_plan.py

The imposition logic is pure Python, so it can be used on its own - for example
to check by hand which page ends up where before wasting paper.
"""

from __future__ import annotations

from booklette import Duplex, SheetOrder, format_plan, impose


def main() -> None:
    print("A 12 page document, single fold, printer defaults:\n")
    print(format_plan(impose(12)))

    print("\nThe same document in the order the pages are read (--order normal):\n")
    print(format_plan(impose(12, order=SheetOrder.NORMAL)))

    print("\nShort-edge duplex, so no side needs rotating:\n")
    print(format_plan(impose(12, duplex=Duplex.SHORT_EDGE, order=SheetOrder.NORMAL)))

    print("\nA 20 page document folded in groups of 8 pages:\n")
    print(format_plan(impose(20, signature_size=8, order=SheetOrder.NORMAL)))

    print("\nA 6 page document - '-' marks the blanks added as padding:\n")
    print(format_plan(impose(6, order=SheetOrder.NORMAL)))


if __name__ == "__main__":
    main()
