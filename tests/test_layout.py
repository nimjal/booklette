"""Tests for the sheet geometry."""

from __future__ import annotations

import pytest

from booklette.layout import (
    Placement,
    Rect,
    build_sheet_layout,
    multiply,
    normalise_offset,
    place,
    rotate_point,
    rotation_matrix,
    visible_size,
)
from booklette.paper import mm_to_points, parse_paper

A4 = parse_paper("a4")
A4_LANDSCAPE_WIDTH = mm_to_points(297.0)
A4_LANDSCAPE_HEIGHT = mm_to_points(210.0)


class TestSheetLayout:
    def test_the_sheet_is_the_paper_turned_landscape(self):
        layout = build_sheet_layout(A4)
        assert layout.width == pytest.approx(A4_LANDSCAPE_WIDTH)
        assert layout.height == pytest.approx(A4_LANDSCAPE_HEIGHT)

    def test_without_margins_the_two_slots_fill_the_sheet(self):
        layout = build_sheet_layout(A4)
        assert layout.left_slot.x == 0
        assert layout.left_slot.right == pytest.approx(layout.width / 2)
        assert layout.right_slot.x == pytest.approx(layout.width / 2)
        assert layout.right_slot.right == pytest.approx(layout.width)

    def test_each_slot_is_a5_shaped(self):
        layout = build_sheet_layout(A4)
        a5_width, a5_height = parse_paper("a5")
        # A5 is defined by rounding, so allow half a millimetre of slack.
        assert layout.left_slot.width == pytest.approx(mm_to_points(a5_width), abs=1.5)
        assert layout.left_slot.height == pytest.approx(mm_to_points(a5_height), abs=1.5)

    def test_margin_is_taken_from_the_outer_edges(self):
        layout = build_sheet_layout(A4, margin_mm=10)
        margin = mm_to_points(10)
        assert layout.left_slot.x == pytest.approx(margin)
        assert layout.left_slot.y == pytest.approx(margin)
        assert layout.left_slot.right == pytest.approx(layout.width / 2)
        assert layout.right_slot.right == pytest.approx(layout.width - margin)

    def test_gutter_is_taken_from_the_fold(self):
        layout = build_sheet_layout(A4, gutter_mm=10)
        gutter = mm_to_points(10)
        assert layout.left_slot.right == pytest.approx(layout.width / 2 - gutter)
        assert layout.right_slot.x == pytest.approx(layout.width / 2 + gutter)

    def test_the_slots_stay_the_same_size(self):
        layout = build_sheet_layout(A4, margin_mm=7, gutter_mm=4)
        assert layout.left_slot.width == pytest.approx(layout.right_slot.width)
        assert layout.left_slot.height == pytest.approx(layout.right_slot.height)

    def test_slot_selection(self):
        layout = build_sheet_layout(A4)
        assert layout.slot(is_right=False) is layout.left_slot
        assert layout.slot(is_right=True) is layout.right_slot

    @pytest.mark.parametrize(("margin", "gutter"), [(-1, 0), (0, -1)])
    def test_negative_spacing_is_rejected(self, margin, gutter):
        with pytest.raises(ValueError, match="cannot be negative"):
            build_sheet_layout(A4, margin_mm=margin, gutter_mm=gutter)

    def test_absurd_spacing_is_rejected(self):
        with pytest.raises(ValueError, match="no room"):
            build_sheet_layout(A4, margin_mm=200)


class TestPlace:
    def test_a_page_is_scaled_down_to_fit_its_slot(self):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, mm_to_points(210), mm_to_points(297))  # A4 portrait

        placement = place(source, layout.left_slot, layout, upside_down=False)

        # An A4 page fits into an A5 slot at roughly 1/sqrt(2).
        assert placement.scale == pytest.approx(0.7071, abs=0.001)
        assert placement.rotate_180 is False

    def test_the_page_is_centred_in_its_slot(self):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, 100, 100)  # square: it cannot fill the tall slot

        placement = place(source, layout.left_slot, layout, upside_down=False)
        scaled = 100 * placement.scale
        left_gap = placement.translate[0] - layout.left_slot.x
        right_gap = layout.left_slot.right - (placement.translate[0] + scaled)

        assert left_gap == pytest.approx(right_gap)
        assert placement.translate[1] == pytest.approx(
            layout.left_slot.y + (layout.left_slot.height - scaled) / 2
        )

    def test_a_page_box_that_does_not_start_at_the_origin_is_shifted_back(self):
        layout = build_sheet_layout(A4)
        source = Rect(30, 20, 400, 600)

        placement = place(source, layout.left_slot, layout, upside_down=False)

        assert placement.source_offset == (-30, -20)

    def test_upside_down_mirrors_through_the_centre_of_the_sheet(self):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, 400, 600)

        upright = place(source, layout.left_slot, layout, upside_down=False)
        flipped = place(source, layout.left_slot, layout, upside_down=True)

        assert flipped.rotate_180 is True
        assert flipped.scale == pytest.approx(upright.scale)
        # A rotated page is anchored by its opposite corner, so the translation
        # is the sheet size minus the upright position.
        assert flipped.translate[0] == pytest.approx(layout.width - upright.translate[0])
        assert flipped.translate[1] == pytest.approx(layout.height - upright.translate[1])

    def test_a_flipped_left_page_covers_the_right_half(self):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, mm_to_points(148), mm_to_points(210))

        flipped = place(source, layout.left_slot, layout, upside_down=True)
        # After the 180 degree turn the page grows towards lower coordinates,
        # so the translation marks its right-hand edge.
        right_edge = flipped.translate[0]
        left_edge = right_edge - source.width * flipped.scale

        assert left_edge >= layout.width / 2 - 1
        assert right_edge == pytest.approx(layout.width, abs=1)

    def test_an_empty_page_is_rejected(self):
        layout = build_sheet_layout(A4)
        with pytest.raises(ValueError, match="no area"):
            place(Rect(0, 0, 0, 100), layout.left_slot, layout, upside_down=False)


class TestRotationHelpers:
    @pytest.mark.parametrize(
        ("degrees", "expected"),
        [(0, (10.0, 5.0)), (90, (5.0, -10.0)), (180, (-10.0, -5.0)), (270, (-5.0, 10.0))],
    )
    def test_quarter_turns_go_clockwise(self, degrees, expected):
        assert rotate_point(10, 5, degrees) == expected

    def test_negative_and_large_angles_wrap_around(self):
        assert rotation_matrix(-90) == rotation_matrix(270)
        assert rotation_matrix(450) == rotation_matrix(90)

    def test_only_quarter_turns_are_supported(self):
        with pytest.raises(ValueError, match="quarter turns"):
            rotation_matrix(45)

    @pytest.mark.parametrize(
        ("rotation", "expected"),
        [(0, (100.0, 200.0)), (90, (200.0, 100.0)), (180, (100.0, 200.0)), (270, (200.0, 100.0))],
    )
    def test_quarter_turns_swap_width_and_height(self, rotation, expected):
        assert visible_size(Rect(0, 0, 100, 200), rotation) == expected

    @pytest.mark.parametrize("rotation", [0, 90, 180, 270])
    def test_normalising_moves_the_page_onto_the_origin(self, rotation):
        source = Rect(17, 23, 100, 200)
        offset_x, offset_y = normalise_offset(source, rotation)

        corners = [
            rotate_point(x, y, rotation)
            for x in (source.x, source.right)
            for y in (source.y, source.top)
        ]
        moved = [(x + offset_x, y + offset_y) for x, y in corners]

        assert min(x for x, _ in moved) == pytest.approx(0)
        assert min(y for _, y in moved) == pytest.approx(0)


class TestMatrix:
    def test_multiplication_applies_the_first_matrix_first(self):
        move = (1.0, 0.0, 0.0, 1.0, 5.0, 0.0)
        grow = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)

        # Move then grow: the move is scaled up as well.
        assert multiply(move, grow)[4] == pytest.approx(10.0)
        # Grow then move: the move is applied afterwards, untouched.
        assert multiply(grow, move)[4] == pytest.approx(5.0)

    def test_placement_maps_the_page_corners_onto_the_slot(self):
        layout = build_sheet_layout(A4, margin_mm=5, gutter_mm=3)
        source = Rect(0, 0, mm_to_points(210), mm_to_points(297))
        slot = layout.right_slot

        placement = place(source, slot, layout, upside_down=False)
        corners = [
            placement.apply(x, y) for x in (source.x, source.right) for y in (source.y, source.top)
        ]

        assert min(x for x, _ in corners) == pytest.approx(slot.x, abs=1)
        assert max(x for x, _ in corners) == pytest.approx(slot.right, abs=1)
        assert min(y for _, y in corners) >= slot.y - 1
        assert max(y for _, y in corners) <= slot.top + 1

    @pytest.mark.parametrize("rotation", [0, 90, 180, 270])
    def test_a_rotated_page_still_lands_inside_its_slot(self, rotation):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, mm_to_points(210), mm_to_points(297))
        slot = layout.left_slot

        placement = place(source, slot, layout, upside_down=False, source_rotation=rotation)
        corners = [
            placement.apply(x, y) for x in (source.x, source.right) for y in (source.y, source.top)
        ]

        assert min(x for x, _ in corners) >= slot.x - 1
        assert max(x for x, _ in corners) <= slot.right + 1
        assert min(y for _, y in corners) >= slot.y - 1
        assert max(y for _, y in corners) <= slot.top + 1

    def test_an_upside_down_page_covers_the_mirrored_slot(self):
        layout = build_sheet_layout(A4)
        source = Rect(0, 0, mm_to_points(210), mm_to_points(297))

        flipped = place(source, layout.left_slot, layout, upside_down=True)
        corners = [
            flipped.apply(x, y) for x in (source.x, source.right) for y in (source.y, source.top)
        ]

        assert min(x for x, _ in corners) >= layout.right_slot.x - 1
        assert max(x for x, _ in corners) <= layout.width + 1

    def test_the_identity_placement_changes_nothing(self):
        placement = Placement(0, (0.0, 0.0), 1.0, False, (0.0, 0.0))
        assert placement.apply(12.5, 34.5) == (12.5, 34.5)
