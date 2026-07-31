"""Tests for what gets drawn on the padding pages.

The filler module produces a PDF content stream as text, so these tests read
that text directly: no PDF library is involved until :mod:`test_builder`.
"""

from __future__ import annotations

import pytest

from booklette.filler import (
    DEFAULT_TITLE,
    FONT_NAME,
    Filler,
    content_stream,
    plan_notes,
)
from booklette.paper import mm_to_points

A4_PORTRAIT = (mm_to_points(210), mm_to_points(297))


def stroke_count(stream: str) -> int:
    """How many lines the stream strokes."""
    return stream.count(" l S")


class TestModes:
    @pytest.mark.parametrize(
        ("filler", "title", "lines"),
        [
            (Filler.NOTES, True, True),
            (Filler.NOTES_PLAIN, True, False),
            (Filler.LINES, False, True),
            (Filler.BLANK, False, False),
        ],
    )
    def test_each_mode_draws_what_it_promises(self, filler, title, lines):
        stream = content_stream(*A4_PORTRAIT, filler)

        assert (f"({DEFAULT_TITLE}) Tj" in stream) is title
        assert (stroke_count(stream) > 0) is lines

    def test_blank_draws_nothing_at_all(self):
        assert content_stream(*A4_PORTRAIT, Filler.BLANK) == ""

    def test_the_heading_uses_the_font_the_builder_registers(self):
        assert f"/{FONT_NAME} " in content_stream(*A4_PORTRAIT, Filler.NOTES)

    def test_the_heading_can_be_changed(self):
        stream = content_stream(*A4_PORTRAIT, Filler.NOTES, title="Ideas")

        assert "(Ideas) Tj" in stream
        assert DEFAULT_TITLE not in stream

    def test_an_empty_heading_leaves_the_lines_alone(self):
        stream = content_stream(*A4_PORTRAIT, Filler.NOTES, title="")

        assert "Tj" not in stream
        assert stroke_count(stream) > 0

    def test_a_heading_only_filler_with_no_heading_draws_nothing(self):
        assert content_stream(*A4_PORTRAIT, Filler.NOTES_PLAIN, title="") == ""


class TestLayout:
    def test_lines_fill_the_page_from_the_top_down(self):
        layout = plan_notes(*A4_PORTRAIT, Filler.NOTES)
        gaps = {
            round(first - second, 3) for first, second in zip(layout.line_ys, layout.line_ys[1:])
        }

        assert len(layout.line_ys) > 10
        assert layout.line_ys == tuple(sorted(layout.line_ys, reverse=True))
        assert gaps == {round(mm_to_points(9), 3)}

    def test_nothing_escapes_the_margins(self):
        width, height = A4_PORTRAIT
        layout = plan_notes(width, height, Filler.NOTES)

        assert 0 < layout.left < layout.right < width
        assert all(0 < y < height for y in layout.line_ys)
        assert layout.title_baseline is not None
        assert max(layout.line_ys) < layout.title_baseline

    def test_wider_spacing_means_fewer_lines(self):
        close = plan_notes(*A4_PORTRAIT, Filler.NOTES, line_spacing_mm=5)
        far = plan_notes(*A4_PORTRAIT, Filler.NOTES, line_spacing_mm=20)

        assert len(close.line_ys) > len(far.line_ys)

    def test_spacing_must_be_positive(self):
        with pytest.raises(ValueError, match="line spacing"):
            plan_notes(*A4_PORTRAIT, Filler.NOTES, line_spacing_mm=0)

    def test_a_tiny_page_is_not_all_margin(self):
        """A business-card page still gets a line or two rather than nothing."""
        layout = plan_notes(mm_to_points(55), mm_to_points(85), Filler.LINES)

        assert layout.left < layout.right
        assert layout.line_ys

    def test_a_page_with_no_area_draws_nothing(self):
        assert plan_notes(0, 0, Filler.NOTES).is_empty


class TestHeadingText:
    def test_brackets_and_backslashes_are_escaped(self):
        stream = content_stream(*A4_PORTRAIT, Filler.NOTES_PLAIN, title=r"Notes (draft) \ 1")
        assert r"(Notes \(draft\) \\ 1) Tj" in stream

    def test_newlines_do_not_break_out_of_the_string(self):
        stream = content_stream(*A4_PORTRAIT, Filler.NOTES_PLAIN, title="one\ntwo")
        assert "(one two) Tj" in stream

    def test_characters_helvetica_cannot_show_are_replaced(self):
        stream = content_stream(*A4_PORTRAIT, Filler.NOTES_PLAIN, title="Notes 中")

        assert "Tj" in stream
        assert "中" not in stream
