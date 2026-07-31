"""Generate a numbered sample PDF, using nothing but the standard library.

Every page carries a big page number, a label and a bar along the top edge, so
that after printing and folding you can see at a glance whether the order and
the orientation are right.

    python examples/make_sample_pdf.py sample.pdf --pages 12

The tests reuse :func:`make_numbered_pdf` as a fixture, which is also why this
file has no third-party imports.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# A4 portrait in PDF points (1 point = 1/72 inch).
A4_PORTRAIT = (595.28, 841.89)


def make_numbered_pdf(
    path: str | Path,
    page_count: int = 12,
    page_size: tuple[float, float] = A4_PORTRAIT,
) -> Path:
    """Write a PDF with ``page_count`` numbered pages and return its path."""
    if page_count < 1:
        raise ValueError("page_count must be at least 1")

    width, height = page_size
    objects: dict[int, bytes] = {}
    page_ids: list[int] = []

    # Object ids 1-3 are fixed: catalog, page tree, font.
    next_id = 4
    for number in range(1, page_count + 1):
        page_id, content_id = next_id, next_id + 1
        next_id += 2

        stream = _page_content(number, width, height).encode("latin-1")
        objects[content_id] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        objects[page_id] = b"<< /Type /Page /Parent 2 0 R /Contents %d 0 R >>" % content_id
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        f"<< /Type /Pages /Count {page_count} /Kids [{kids}] "
        f"/MediaBox [0 0 {width:.2f} {height:.2f}] "
        f"/Resources << /Font << /F1 3 0 R >> >> >>"
    ).encode("latin-1")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    path = Path(path)
    path.write_bytes(_serialise(objects))
    return path


def _page_content(number: int, width: float, height: float) -> str:
    """The drawing commands for a single numbered page."""
    big = f"{number}"
    label = f"page {number}"
    return "\n".join(
        [
            # A bar across the top, so "which way is up" is obvious on paper.
            f"0.85 g 0 {height - 40:.2f} {width:.2f} 40 re f",
            # A thin frame around the page.
            f"0.6 G 1 w 20 20 {width - 40:.2f} {height - 80:.2f} re S",
            # "TOP" inside the bar.
            f"0 g BT /F1 14 Tf 30 {height - 28:.2f} Td (TOP - {_escape(label)}) Tj ET",
            # The page number, roughly centred.
            f"BT /F1 160 Tf {width / 2 - 45 * len(big) / 2:.2f} {height / 2 - 55:.2f} Td "
            f"({_escape(big)}) Tj ET",
            # The label again at the bottom.
            f"BT /F1 14 Tf 30 40 Td ({_escape(label)}) Tj ET",
        ]
    )


def _escape(text: str) -> str:
    """Escape the characters that are special inside a PDF string literal."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _serialise(objects: dict[int, bytes]) -> bytes:
    """Lay the objects out into a complete PDF file with a cross-reference table."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}

    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += b"%d 0 obj\n" % object_id + objects[object_id] + b"\nendobj\n"

    # The cross-reference table maps object ids to byte offsets in the file.
    start_xref = len(out)
    count = len(objects) + 1
    out += b"xref\n0 %d\n" % count
    out += b"0000000000 65535 f \n"
    for object_id in sorted(objects):
        out += b"%010d 00000 n \n" % offsets[object_id]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (count, start_xref)
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default="sample.pdf", help="file to write")
    parser.add_argument("--pages", type=int, default=12, help="number of pages (default: 12)")
    args = parser.parse_args()

    path = make_numbered_pdf(args.output, args.pages)
    print(f"Wrote {path} with {args.pages} numbered pages")


if __name__ == "__main__":
    main()
