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
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from .filler import DEFAULT_TITLE, FONT_NAME, Filler, content_stream
from .imposition import (
    BACK_COVER_PAGE,
    Duplex,
    Sheet,
    SheetOrder,
    SheetSide,
    count_blank_pages,
    impose,
    is_padding,
)
from .layout import Rect, SheetLayout, build_sheet_layout, place, visible_size
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
    output face down (so sheets are emitted in reading order) and duplex
    printing that flips on the long edge. The padding pages at the back become
    ruled note paper, apart from the back cover.
    """

    #: Paper name (``"a4"``, ``"letter"``, ...) or ``"WIDTHxHEIGHT"`` in mm.
    paper: str = "a4"
    #: How the printer turns the paper over between sides.
    duplex: Duplex = Duplex.LONG_EDGE
    #: Order in which sheets are written to the output file.
    order: SheetOrder = SheetOrder.NORMAL
    #: Pages per folded group; ``0`` folds the whole document at once.
    signature_size: int = 0
    #: Whitespace at the outer edges of the sheet, in millimetres.
    margin_mm: float = 0.0
    #: Extra whitespace either side of the fold, in millimetres.
    gutter_mm: float = 0.0
    #: Mirror the layout for right-to-left languages.
    right_to_left: bool = False
    #: What to print on the padding pages at the back - see :class:`Filler`.
    filler: Filler = Filler.NOTES
    #: Heading for the notes fillers.
    filler_title: str = DEFAULT_TITLE
    #: Apply the filler to the back cover too, instead of leaving it empty.
    fill_back_cover: bool = False
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
    #: Padding pages added to fill the last sheet(s), filled or not.
    blank_pages: int
    sheet_size_mm: tuple[float, float]
    #: How many of those padding pages were printed as note paper.
    filled_pages: int = 0
    plan: list[Sheet] = field(repr=False, default_factory=list)

    @property
    def output_pages(self) -> int:
        """Number of pages in the generated PDF (two per sheet: front and back)."""
        return self.sheets * 2

    @property
    def empty_pages(self) -> int:
        """Padding pages left completely empty, the back cover among them."""
        return self.blank_pages - self.filled_pages


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

    filling = _Filling.for_options(reader, options)

    writer = PdfWriter()
    for sheet in sheets:
        for side in sheet.sides:
            _render_side(writer, reader, side, layout, filling)

    _copy_metadata(reader, writer)
    writer.write(target)
    writer.close()

    return BookletResult(
        source_pages=page_count,
        sheets=len(sheets),
        blank_pages=count_blank_pages(sheets),
        sheet_size_mm=options.sheet_size_mm(),
        filled_pages=filling.count_filled(sheets),
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


@dataclass(frozen=True)
class _Filling:
    """The page drawn on padding slots, or ``None`` where they stay empty.

    One prepared page is reused for every padding slot: it carries no source
    material, so the same object can be merged onto as many sheets as needed.
    The back cover gets its own slot in this pair because it is normally left
    empty even when the rest of the padding is printed.
    """

    padding: PageObject | None
    back_cover: PageObject | None

    @classmethod
    def for_options(cls, reader: PdfReader, options: BookletOptions) -> _Filling:
        """Prepare the filler page described by ``options``, if it draws anything."""
        page = _build_filler_page(_source_page_size(reader), options)
        if page is None:
            return cls(padding=None, back_cover=None)
        return cls(padding=page, back_cover=page if options.fill_back_cover else None)

    def page_for(self, page_number: int) -> PageObject | None:
        """The page to draw for ``page_number``, or ``None`` to leave it empty.

        Source pages are not this object's business and always give ``None``.
        """
        if not is_padding(page_number):
            return None
        return self.back_cover if page_number == BACK_COVER_PAGE else self.padding

    def count_filled(self, sheets: list[Sheet]) -> int:
        """How many padding slots in ``sheets`` this filling actually prints on."""
        return sum(
            1
            for sheet in sheets
            for side in sheet.sides
            for page in side.pages
            if self.page_for(page) is not None
        )


def _render_side(
    writer: PdfWriter,
    reader: PdfReader,
    side: SheetSide,
    layout: SheetLayout,
    filling: _Filling,
) -> None:
    """Add one printed side (two pages, side by side) to ``writer``."""
    sheet_page = writer.add_blank_page(width=layout.width, height=layout.height)

    for page_number, is_right in ((side.left, False), (side.right, True)):
        if is_padding(page_number):
            source_page = filling.page_for(page_number)
            if source_page is None:
                continue  # Padding with nothing on it: leave the half empty.
            rotation = 0
        else:
            source_page = reader.pages[page_number - 1]
            rotation = _page_rotation(source_page)

        placement = place(
            _visible_box(source_page),
            layout.slot(is_right=is_right),
            layout,
            upside_down=side.rotated,
            source_rotation=rotation,
        )
        # Placement.matrix() is the whole scale/rotate/move recipe as a single
        # PDF matrix, which is exactly what pypdf wants for a merge.
        sheet_page.merge_transformed_page(source_page, placement.matrix())


def _source_page_size(reader: PdfReader) -> tuple[float, float]:
    """The size a filler page should have: that of the document's first page.

    Taking it from the document rather than from the sheet means a filler is
    scaled into its half of the sheet exactly like a real page, so the ruled
    area lines up with the text area of the pages before it.
    """
    first = reader.pages[0]
    return visible_size(_visible_box(first), _page_rotation(first))


def _build_filler_page(size: tuple[float, float], options: BookletOptions) -> PageObject | None:
    """Build a standalone page carrying the notes drawing described by ``options``.

    ``None`` when the options draw nothing at all, so that a padding page is
    left untouched rather than covered with an empty page.

    The page belongs to no document: it exists only to be merged onto sheets,
    which is why the content stream and the Helvetica used for the heading are
    attached by hand instead of going through a writer.
    """
    width, height = size
    drawing = content_stream(width, height, options.filler, title=options.filler_title)
    if not drawing:
        return None

    page = PageObject.create_blank_page(width=width, height=height)
    stream = DecodedStreamObject()
    stream.set_data(drawing.encode("latin-1"))
    page[NameObject("/Contents")] = stream

    if options.filler.draws_title and options.filler_title:
        page[NameObject("/Resources")] = _helvetica_resources()
    return page


def _helvetica_resources() -> DictionaryObject:
    """A ``/Resources`` dictionary holding the one font the heading needs.

    Helvetica is one of the fourteen fonts every PDF reader is required to
    provide, so nothing has to be embedded. It is asked for with WinAnsi
    encoding, which agrees with the Latin-1 bytes :mod:`booklette.filler` writes
    - without it an accented heading would come out as the wrong glyph.
    """
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    font[NameObject("/Encoding")] = NameObject("/WinAnsiEncoding")

    fonts = DictionaryObject()
    fonts[NameObject(f"/{FONT_NAME}")] = font

    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts
    return resources


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
