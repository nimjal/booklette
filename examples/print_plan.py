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

    print("\nThe same document last sheet first (--order reverse):\n")
    print(format_plan(impose(12, order=SheetOrder.REVERSE)))

    print("\nShort-edge duplex, so no side needs rotating:\n")
    print(format_plan(impose(12, duplex=Duplex.SHORT_EDGE)))

    print("\nA 20 page document folded in groups of 8 pages:\n")
    print(format_plan(impose(20, signature_size=8)))

    print("\nA 6 page document - '-' is a padding page, 'bc' the back cover:\n")
    print(format_plan(impose(6)))


if __name__ == "__main__":
    main()
