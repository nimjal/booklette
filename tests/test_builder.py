"""End-to-end tests: build real PDFs and inspect where the pages landed.

The sample pages made by ``examples/make_sample_pdf.py`` each carry a "page N"
label, so after imposing we can read the output back and check which half of
which sheet every source page ended up on, and whether it was turned upside
down.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pypdf import PdfReader, PdfWriter

from booklette import (
    BookletError,
    BookletOptions,
    Duplex,
    Filler,
    SheetOrder,
    create_booklet,
)
from booklette.paper import mm_to_points


@dataclass(frozen=True)
class PlacedPage:
    """Where one source page ended up on a sheet side."""

    number: int
    x: float
    y: float
    upside_down: bool


def placed_pages(page) -> list[PlacedPage]:
    """Read back the source pages drawn on one output page.

    ``cm`` is the matrix this package applied when merging the page, ``tm`` is
    the position of the text inside the original page; multiplying the two gives
    the position on the sheet.
    """
    found: list[PlacedPage] = []

    def visitor(text, cm, tm, font_dict, font_size):
        label = text.strip()
        if not label.startswith("page "):
            return
        x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
        y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
        found.append(PlacedPage(int(label.split()[1]), x, y, upside_down=cm[0] < 0))

    page.extract_text(visitor_text=visitor)
    return found


def page_numbers(page) -> list[int]:
    """The source page numbers drawn on one output page, left half first."""
    return [placed.number for placed in sorted(placed_pages(page), key=lambda p: p.x)]


def heading_positions(page, heading: str = "Notes:") -> list[float]:
    """The x position of every filler heading drawn on one output page."""
    found: list[float] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if heading in text:
            found.append(cm[0] * tm[4] + cm[2] * tm[5] + cm[4])

    page.extract_text(visitor_text=visitor)
    return found


def ruled_lines(page) -> int:
    """How many ruled lines were drawn onto one output page.

    ``l`` is the "line to" operator; pypdf re-wraps the operators it merges, so
    the stream is tokenised rather than searched for a fixed spelling.
    """
    operators = page.get_contents().get_data().decode("latin-1").split()
    return operators.count("l")


class TestOutputShape:
    def test_four_source_pages_make_one_sheet(self, numbered_pdf, tmp_path):
        result = create_booklet(numbered_pdf(4), tmp_path / "out.pdf")

        assert result.sheets == 1
        assert result.output_pages == 2
        assert result.blank_pages == 0
        assert len(PdfReader(tmp_path / "out.pdf").pages) == 2

    def test_pages_are_padded_up_to_a_whole_sheet(self, numbered_pdf, tmp_path):
        result = create_booklet(numbered_pdf(5), tmp_path / "out.pdf")

        assert result.sheets == 2
        assert result.blank_pages == 3

    def test_sheets_are_a4_landscape_by_default(self, numbered_pdf, tmp_path):
        create_booklet(numbered_pdf(4), tmp_path / "out.pdf")

        box = PdfReader(tmp_path / "out.pdf").pages[0].mediabox
        assert float(box.width) == pytest.approx(mm_to_points(297), abs=0.5)
        assert float(box.height) == pytest.approx(mm_to_points(210), abs=0.5)

    def test_paper_size_is_configurable(self, numbered_pdf, tmp_path):
        create_booklet(numbered_pdf(4), tmp_path / "out.pdf", BookletOptions(paper="a3"))

        box = PdfReader(tmp_path / "out.pdf").pages[0].mediabox
        assert float(box.width) == pytest.approx(mm_to_points(420), abs=0.5)

    def test_writes_to_an_open_file_object(self, numbered_pdf, tmp_path):
        target = tmp_path / "stream.pdf"
        with target.open("wb") as handle:
            create_booklet(numbered_pdf(4), handle)

        assert len(PdfReader(target).pages) == 2


class TestPageOrder:
    def test_an_eight_page_booklet_is_imposed_correctly(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(8),
            tmp_path / "out.pdf",
            BookletOptions(order=SheetOrder.NORMAL),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        # The back sides are rotated, which swaps their halves on the sheet.
        assert [page_numbers(page) for page in pages] == [[8, 1], [7, 2], [6, 3], [5, 4]]

    def test_reverse_order_prints_the_last_sheet_first(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(8),
            tmp_path / "out.pdf",
            BookletOptions(order=SheetOrder.REVERSE),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert [page_numbers(page) for page in pages] == [[6, 3], [5, 4], [8, 1], [7, 2]]

    def test_every_source_page_is_used_exactly_once(self, numbered_pdf, tmp_path):
        create_booklet(numbered_pdf(11), tmp_path / "out.pdf")

        pages = PdfReader(tmp_path / "out.pdf").pages
        found = [number for page in pages for number in page_numbers(page)]
        assert sorted(found) == list(range(1, 12))


class TestDuplex:
    def test_long_edge_duplex_turns_the_back_upside_down(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(4),
            tmp_path / "out.pdf",
            BookletOptions(duplex=Duplex.LONG_EDGE, order=SheetOrder.NORMAL),
        )

        front, back = PdfReader(tmp_path / "out.pdf").pages
        assert [placed.upside_down for placed in placed_pages(front)] == [False, False]
        assert [placed.upside_down for placed in placed_pages(back)] == [True, True]

    def test_short_edge_duplex_leaves_both_sides_upright(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(4),
            tmp_path / "out.pdf",
            BookletOptions(duplex=Duplex.SHORT_EDGE, order=SheetOrder.NORMAL),
        )

        front, back = PdfReader(tmp_path / "out.pdf").pages
        assert [page_numbers(page) for page in (front, back)] == [[4, 1], [2, 3]]
        assert not any(placed.upside_down for placed in placed_pages(back))

    def test_a_leaf_keeps_its_two_pages_back_to_back(self, numbered_pdf, tmp_path):
        """Page 1 must be printed on the back of the same half-sheet as page 2.

        Long-edge duplex turns the paper about an axis perpendicular to the
        fold, so each half of the paper stays behind the same half of the sheet.
        Rotating the back side by 180 degrees is what moves page 2 onto the
        right half - the other face of the leaf that carries page 1.
        """
        create_booklet(
            numbered_pdf(8),
            tmp_path / "out.pdf",
            BookletOptions(order=SheetOrder.NORMAL),
        )

        front, back = PdfReader(tmp_path / "out.pdf").pages[:2]
        middle = float(front.mediabox.width) / 2

        page_one = next(p for p in placed_pages(front) if p.number == 1)
        page_two = next(p for p in placed_pages(back) if p.number == 2)
        assert page_one.x > middle  # right half of the front
        assert page_two.x > middle  # mirrored onto the same half of the paper


class TestFiller:
    """The padding pages at the back come out as note paper by default.

    A five page document is imposed as eight, so pages 6, 7 and 8 are padding.
    Page 8 is the back cover and lands on the left half of the first sheet; the
    other two get the notes.
    """

    def test_padding_pages_are_ruled_as_notes(self, numbered_pdf, tmp_path):
        result = create_booklet(numbered_pdf(5), tmp_path / "out.pdf")

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert result.blank_pages == 3
        assert result.filled_pages == 2
        assert result.empty_pages == 1
        assert sum(len(heading_positions(page)) for page in pages) == 2
        assert all(ruled_lines(page) > 5 for page in pages if heading_positions(page))

    def test_the_back_cover_is_left_empty(self, numbered_pdf, tmp_path):
        create_booklet(numbered_pdf(5), tmp_path / "out.pdf")

        # The back cover shares its sheet side with page 1, and stays blank.
        first_side = PdfReader(tmp_path / "out.pdf").pages[0]
        assert page_numbers(first_side) == [1]
        assert heading_positions(first_side) == []

    def test_the_back_cover_can_be_filled_too(self, numbered_pdf, tmp_path):
        result = create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(fill_back_cover=True),
        )

        first_side = PdfReader(tmp_path / "out.pdf").pages[0]
        middle = float(first_side.mediabox.width) / 2
        headings = heading_positions(first_side)

        assert result.filled_pages == 3
        assert result.empty_pages == 0
        # The back cover is the left half of the first sheet.
        assert len(headings) == 1
        assert headings[0] < middle

    def test_blank_filler_leaves_every_padding_page_empty(self, numbered_pdf, tmp_path):
        result = create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(filler=Filler.BLANK),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert result.filled_pages == 0
        assert not any(heading_positions(page) for page in pages)
        assert not any(ruled_lines(page) for page in pages)

    def test_lines_only_leaves_out_the_heading(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(filler=Filler.LINES),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert not any(heading_positions(page) for page in pages)
        assert sum(ruled_lines(page) for page in pages) > 10

    def test_notes_plain_leaves_out_the_lines(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(filler=Filler.NOTES_PLAIN),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert sum(len(heading_positions(page)) for page in pages) == 2
        assert not any(ruled_lines(page) for page in pages)

    def test_the_heading_can_be_changed(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(filler_title="Ideas"),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert sum(len(heading_positions(page, "Ideas")) for page in pages) == 2
        assert not any(heading_positions(page) for page in pages)

    def test_a_heading_only_filler_with_no_heading_draws_nothing(self, numbered_pdf, tmp_path):
        result = create_booklet(
            numbered_pdf(5),
            tmp_path / "out.pdf",
            BookletOptions(filler=Filler.NOTES_PLAIN, filler_title=""),
        )

        assert result.filled_pages == 0
        assert result.empty_pages == 3

    def test_a_document_that_fills_its_sheets_gets_no_notes(self, numbered_pdf, tmp_path):
        result = create_booklet(numbered_pdf(8), tmp_path / "out.pdf")

        pages = PdfReader(tmp_path / "out.pdf").pages
        assert result.filled_pages == 0
        assert not any(heading_positions(page) for page in pages)

    def test_notes_land_on_their_own_half_of_the_sheet(self, numbered_pdf, tmp_path):
        """A filler is placed like any other page: in one slot, not across the fold."""
        create_booklet(numbered_pdf(5), tmp_path / "out.pdf", BookletOptions(margin_mm=5))

        second_side = PdfReader(tmp_path / "out.pdf").pages[1]
        middle = float(second_side.mediabox.width) / 2
        page_two = next(p for p in placed_pages(second_side) if p.number == 2)

        # Page 2 and the notes page share this side, one half each.
        assert len(heading_positions(second_side)) == 1
        assert (heading_positions(second_side)[0] < middle) != (page_two.x < middle)

    def test_every_notes_page_is_drawn_from_the_same_prepared_page(self, numbered_pdf, tmp_path):
        """Reusing one filler page must not make the second copy come out empty."""
        create_booklet(numbered_pdf(9), tmp_path / "out.pdf")

        pages = PdfReader(tmp_path / "out.pdf").pages
        filled = [ruled_lines(page) for page in pages if heading_positions(page)]
        assert len(filled) == 2
        assert len(set(filled)) == 1  # both got the same drawing


class TestLayoutOptions:
    def test_margins_shrink_the_pages(self, numbered_pdf, tmp_path):
        source = numbered_pdf(4)
        create_booklet(source, tmp_path / "plain.pdf")
        create_booklet(source, tmp_path / "margins.pdf", BookletOptions(margin_mm=15))

        def label_x(name):
            page = PdfReader(tmp_path / name).pages[0]
            return next(p for p in placed_pages(page) if p.number == 4).x

        # The left page starts further from the edge once there is a margin.
        assert label_x("margins.pdf") > label_x("plain.pdf")

    def test_right_to_left_puts_page_one_on_the_left(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(8),
            tmp_path / "out.pdf",
            BookletOptions(right_to_left=True, order=SheetOrder.NORMAL),
        )

        front = PdfReader(tmp_path / "out.pdf").pages[0]
        assert page_numbers(front) == [1, 8]

    def test_signatures_split_the_book_into_folded_groups(self, numbered_pdf, tmp_path):
        create_booklet(
            numbered_pdf(16),
            tmp_path / "out.pdf",
            BookletOptions(signature_size=8, order=SheetOrder.NORMAL),
        )

        pages = PdfReader(tmp_path / "out.pdf").pages
        first_group = {number for page in pages[:4] for number in page_numbers(page)}
        assert first_group == {1, 2, 3, 4, 5, 6, 7, 8}

    def test_pages_with_a_rotation_flag_keep_their_visual_orientation(self, numbered_pdf, tmp_path):
        """A /Rotate flag is applied by viewers, so it must be applied here too."""
        source = tmp_path / "rotated.pdf"
        writer = PdfWriter()
        for page in PdfReader(numbered_pdf(4)).pages:
            writer.add_page(page).rotate(90)
        writer.write(source)

        create_booklet(source, tmp_path / "out.pdf", BookletOptions(order=SheetOrder.NORMAL))

        page = PdfReader(tmp_path / "out.pdf").pages[0]
        placed = placed_pages(page)
        middle = float(page.mediabox.width) / 2
        # Both pages are still there, one per half of the sheet, rather than
        # both being squashed into a corner by an unapplied rotation.
        assert {item.number for item in placed} == {4, 1}
        assert min(item.x for item in placed) < middle < max(item.x for item in placed)


class TestErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(BookletError, match="No such file"):
            create_booklet(tmp_path / "nope.pdf", tmp_path / "out.pdf")

    def test_unknown_paper_size(self, numbered_pdf, tmp_path):
        with pytest.raises(ValueError, match="Unknown paper size"):
            create_booklet(numbered_pdf(4), tmp_path / "out.pdf", BookletOptions(paper="a99"))

    def test_result_carries_the_plan(self, numbered_pdf, tmp_path):
        result = create_booklet(numbered_pdf(8), tmp_path / "out.pdf")

        assert len(result.plan) == result.sheets
        assert result.plan[0].front.pages != result.plan[0].back.pages
