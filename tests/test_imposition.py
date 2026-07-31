"""Tests for the page ordering."""

from __future__ import annotations

import pytest

from booklette.imposition import (
    BACK_COVER_PAGE,
    BLANK_PAGE,
    Duplex,
    SheetOrder,
    count_blank_pages,
    format_plan,
    impose,
    is_padding,
    pad_to_multiple_of_four,
    split_into_signatures,
)


def sides(sheets):
    """Flatten sheets into ``[(front pages), (back pages), ...]`` for easy asserts."""
    return [side.pages for sheet in sheets for side in sheet.sides]


class TestPadding:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(1, 4), (2, 4), (3, 4), (4, 4), (5, 8), (8, 8), (9, 12)],
    )
    def test_pads_up_to_a_whole_sheet(self, count, expected):
        assert len(pad_to_multiple_of_four(list(range(1, count + 1)))) == expected

    def test_padding_uses_blank_marker(self):
        assert pad_to_multiple_of_four([1, 2]) == [1, 2, BLANK_PAGE, BLANK_PAGE]

    def test_a_full_sheet_is_left_alone(self):
        assert pad_to_multiple_of_four([1, 2, 3, 4]) == [1, 2, 3, 4]


class TestSignatures:
    def test_zero_means_one_signature(self):
        assert split_into_signatures([1, 2, 3, 4, 5, 6, 7, 8], 0) == [[1, 2, 3, 4, 5, 6, 7, 8]]

    def test_splits_and_pads_the_last_group(self):
        assert split_into_signatures(list(range(1, 11)), 4) == [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, BLANK_PAGE, BLANK_PAGE],
        ]

    def test_size_must_be_a_multiple_of_four(self):
        with pytest.raises(ValueError, match="multiple of 4"):
            split_into_signatures(list(range(1, 21)), 6)

    def test_size_larger_than_the_document_is_a_single_signature(self):
        assert split_into_signatures([1, 2, 3, 4], 64) == [[1, 2, 3, 4]]


class TestImpose:
    def test_the_classic_eight_page_booklet(self):
        assert sides(impose(8, order=SheetOrder.NORMAL)) == [
            (8, 1),
            (2, 7),
            (6, 3),
            (4, 5),
        ]

    def test_sixteen_pages_match_the_table_in_the_docs(self):
        assert sides(impose(16, order=SheetOrder.NORMAL)) == [
            (16, 1),
            (2, 15),
            (14, 3),
            (4, 13),
            (12, 5),
            (6, 11),
            (10, 7),
            (8, 9),
        ]

    def test_short_documents_are_padded_with_blanks(self):
        # Five pages need two sheets; the three missing pages become padding,
        # and - as in any printed booklet - they end up at the back. The very
        # last of them is the back cover, which is named apart from the rest.
        assert sides(impose(5, order=SheetOrder.NORMAL)) == [
            (BACK_COVER_PAGE, 1),
            (2, BLANK_PAGE),
            (BLANK_PAGE, 3),
            (4, 5),
        ]

    def test_every_source_page_appears_exactly_once(self):
        pages = [page for side in sides(impose(23)) for page in side if not is_padding(page)]
        assert sorted(pages) == list(range(1, 24))

    def test_sheets_come_out_in_reading_order_by_default(self):
        assert impose(16) == impose(16, order=SheetOrder.NORMAL)

    def test_reverse_order_flips_sheets_but_not_their_sides(self):
        normal = impose(16, order=SheetOrder.NORMAL)
        reversed_ = impose(16, order=SheetOrder.REVERSE)

        assert reversed_ == list(reversed(normal))
        # Front still comes before back within each sheet.
        assert all(not sheet.front.is_back and sheet.back.is_back for sheet in reversed_)

    def test_right_to_left_mirrors_each_side(self):
        left_to_right = sides(impose(8, order=SheetOrder.NORMAL))
        right_to_left = sides(impose(8, order=SheetOrder.NORMAL, right_to_left=True))

        assert right_to_left == [tuple(reversed(side)) for side in left_to_right]

    def test_long_edge_duplex_rotates_only_the_back(self):
        sheet = impose(8, duplex=Duplex.LONG_EDGE)[0]
        assert sheet.back.rotated is True
        assert sheet.front.rotated is False

    def test_short_edge_duplex_rotates_nothing(self):
        sheet = impose(8, duplex=Duplex.SHORT_EDGE)[0]
        assert sheet.back.rotated is False
        assert sheet.front.rotated is False

    def test_signatures_are_numbered(self):
        sheets = impose(16, signature_size=8, order=SheetOrder.NORMAL)
        assert [sheet.signature for sheet in sheets] == [0, 0, 1, 1]

    def test_pages_stay_inside_their_signature(self):
        sheets = impose(16, signature_size=8, order=SheetOrder.NORMAL)
        first = {page for side in sides(sheets[:2]) for page in side}
        assert first == {1, 2, 3, 4, 5, 6, 7, 8}

    def test_rejects_empty_documents(self):
        with pytest.raises(ValueError, match="at least one page"):
            impose(0)


class TestBackCover:
    """The last padding page is the outside of the back cover, and is named."""

    def test_the_last_padding_page_is_the_back_cover(self):
        pages = [page for side in sides(impose(6)) for page in side]
        assert pages.count(BACK_COVER_PAGE) == 1
        assert pages.count(BLANK_PAGE) == 1

    def test_it_lands_on_the_front_of_the_first_sheet(self):
        # Folded, that half-sheet is the outermost leaf: cover and back cover.
        first = impose(6, order=SheetOrder.NORMAL)[0]
        assert first.front.left == BACK_COVER_PAGE
        assert first.front.right == 1

    def test_a_full_document_has_no_back_cover_marker(self):
        pages = [page for side in sides(impose(8)) for page in side]
        assert BACK_COVER_PAGE not in pages

    def test_only_the_last_signature_is_padded(self):
        sheets = impose(10, signature_size=4, order=SheetOrder.NORMAL)
        pages = [page for side in sides(sheets) for page in side]
        assert pages.count(BACK_COVER_PAGE) == 1
        # The back cover belongs to the last folded group, not the first.
        assert BACK_COVER_PAGE in [page for side in sides(sheets[-1:]) for page in side]

    def test_padding_is_recognised_whatever_it_is_called(self):
        assert is_padding(BLANK_PAGE)
        assert is_padding(BACK_COVER_PAGE)
        assert not is_padding(1)


class TestReporting:
    def test_counts_padding_pages(self):
        assert count_blank_pages(impose(5)) == 3
        assert count_blank_pages(impose(8)) == 0

    def test_plan_marks_blanks_and_rotation(self):
        plan = format_plan(impose(6, order=SheetOrder.NORMAL))
        assert "sheet 1/2" in plan
        assert "-" in plan  # the padding pages
        assert "rotated 180" in plan

    def test_plan_marks_the_back_cover(self):
        assert " bc " in format_plan(impose(6))
        assert " bc " not in format_plan(impose(8))
