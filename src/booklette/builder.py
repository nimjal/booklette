"""Turn a normal PDF into a printable booklet PDF.

This is the only module that talks to :mod:`pypdf`; the page ordering lives in
:mod:`booklette.imposition` and the geometry in
:mod:`booklette.layout`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Union

from pypdf import PageObject, PdfReader, PdfWriter

from .imposition import (
    BLANK_PAGE,
    Duplex,
    Sheet,
    SheetOrder,
    SheetSide,
    count_blank_pages,
    impose,
)
from .layout import Rect, SheetLayout, build_sheet_layout, place
from .paper import landscape, parse_paper

#: Anything :mod:`pypdf` can read from or write to.
PdfSource = Union[str, os.PathLike, IO[bytes]]
PdfTarget = Union[str, os.PathLike, IO[bytes]]


class BookletError(RuntimeError):
    """Raised when a document cannot be turned into a booklet."""


@dataclass
class BookletOptions:
    """Everything that can be tuned about the output.

    The defaults describe the common case: A4 paper, a printer that stacks its
    output face up (so sheets are emitted last-first) and duplex printing that
    flips on the long edge.
    """

    #: Paper name (``"a4"``, ``"letter"``, ...) or ``"WIDTHxHEIGHT"`` in mm.
    paper: str = "a4"
    #: How the printer turns the paper over between sides.
    duplex: Duplex = Duplex.LONG_EDGE
    #: Order in which sheets are written to the output file.
    order: SheetOrder = SheetOrder.REVERSE
    #: Pages per folded group; ``0`` folds the whole document at once.
    signature_size: int = 0
    #: Whitespace at the outer edges of the sheet, in millimetres.
    margin_mm: float = 0.0
    #: Extra whitespace either side of the fold, in millimetres.
    gutter_mm: float = 0.0
    #: Mirror the layout for right-to-left languages.
    right_to_left: bool = False
    #: Password for encrypted source documents.
    password: str | None = None

    def sheet_size_mm(self) -> tuple[float, float]:
        """The landscape ``(width, height)`` of one sheet, in millimetres."""
        return landscape(parse_paper(self.paper))


@dataclass
class BookletResult:
    """Summary of a conversion, handy for logging and for the CLI output."""

    source_pages: int
    sheets: int
    blank_pages: int
    sheet_size_mm: tuple[float, float]
    plan: list[Sheet] = field(repr=False, default_factory=list)

    @property
    def output_pages(self) -> int:
        """Number of pages in the generated PDF (two per sheet: front and back)."""
        return self.sheets * 2


def create_booklet(
    source: PdfSource,
    target: PdfTarget,
    options: BookletOptions | None = None,
) -> BookletResult:
    """Impose ``source`` into a booklet and write it to ``target``.

    :param source: path (or open binary file) of the PDF to convert.
    :param target: path (or open binary file) to write the booklet to.
    :param options: conversion settings; defaults to :class:`BookletOptions`.
    :returns: a :class:`BookletResult` describing what was produced.
    :raises BookletError: if the document is empty or cannot be decrypted.
    """
    options = options or BookletOptions()
    reader = _open_reader(source, options.password)

    page_count = len(reader.pages)
    if page_count == 0:
        raise BookletError("The source PDF has no pages")

    sheets = impose(
        page_count,
        signature_size=options.signature_size,
        duplex=options.duplex,
        order=options.order,
        right_to_left=options.right_to_left,
    )
    layout = build_sheet_layout(
        parse_paper(options.paper),
        margin_mm=options.margin_mm,
        gutter_mm=options.gutter_mm,
    )

    writer = PdfWriter()
    for sheet in sheets:
        for side in sheet.sides:
            _render_side(writer, reader, side, layout)

    _copy_metadata(reader, writer)
    writer.write(target)
    writer.close()

    return BookletResult(
        source_pages=page_count,
        sheets=len(sheets),
        blank_pages=count_blank_pages(sheets),
        sheet_size_mm=options.sheet_size_mm(),
        plan=sheets,
    )


def _open_reader(source: PdfSource, password: str | None) -> PdfReader:
    """Open ``source``, decrypting it if necessary."""
    try:
        reader = PdfReader(source)
    except FileNotFoundError as error:
        raise BookletError(f"No such file: {source}") from error

    # An empty password covers PDFs that are only protected against editing.
    if reader.is_encrypted and reader.decrypt(password or "") == 0:
        raise BookletError("The source PDF is encrypted. Provide the password with --password.")
    return reader


def _render_side(
    writer: PdfWriter,
    reader: PdfReader,
    side: SheetSide,
    layout: SheetLayout,
) -> None:
    """Add one printed side (two source pages) to ``writer``."""
    sheet_page = writer.add_blank_page(width=layout.width, height=layout.height)

    for page_number, is_right in ((side.left, False), (side.right, True)):
        if page_number == BLANK_PAGE:
            continue  # Padding: leave that half of the sheet empty.
        source_page = reader.pages[page_number - 1]
        placement = place(
            _visible_box(source_page),
            layout.slot(is_right=is_right),
            layout,
            upside_down=side.rotated,
            source_rotation=_page_rotation(source_page),
        )
        # Placement.matrix() is the whole scale/rotate/move recipe as a single
        # PDF matrix, which is exactly what pypdf wants for a merge.
        sheet_page.merge_transformed_page(source_page, placement.matrix())


def _page_rotation(page: PageObject) -> int:
    """The page's ``/Rotate`` flag, normalised to 0, 90, 180 or 270.

    Viewers apply this rotation when displaying the page, so the booklet has to
    apply it too - otherwise a page that looks upright on screen would land on
    its side on the sheet.
    """
    rotation = int(page.rotation or 0) % 360
    # The PDF specification only allows quarter turns; be forgiving about files
    # that do not follow it.
    return round(rotation / 90) * 90 % 360


def _visible_box(page: PageObject) -> Rect:
    """The area of ``page`` a reader actually shows, as a :class:`Rect`.

    The crop box wins over the media box when both are present, because that is
    what a viewer (and a printer) displays.
    """
    box = page.cropbox if page.cropbox is not None else page.mediabox
    return Rect(
        x=float(box.left),
        y=float(box.bottom),
        width=float(box.width),
        height=float(box.height),
    )


def _copy_metadata(reader: PdfReader, writer: PdfWriter) -> None:
    """Carry the title and author across, and record who produced the file."""
    metadata = {"/Producer": "booklette"}
    source_metadata = reader.metadata or {}
    for key in ("/Title", "/Author", "/Subject"):
        value = source_metadata.get(key)
        if value:
            metadata[key] = str(value)
    writer.add_metadata(metadata)


def default_output_path(source: str | os.PathLike, target: str | os.PathLike | None = None) -> Path:
    """Choose an output path: ``target`` if given, else ``<source>-booklet.pdf``."""
    if target is not None:
        return Path(target)
    source_path = Path(source)
    return source_path.with_name(f"{source_path.stem}-booklet.pdf")
