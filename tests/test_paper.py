"""Tests for paper sizes and unit conversions."""

from __future__ import annotations

import pytest

from booklette.paper import (
    PAPER_SIZES_MM,
    landscape,
    mm_to_points,
    parse_paper,
    points_to_mm,
)


class TestUnits:
    def test_an_inch_is_seventy_two_points(self):
        assert mm_to_points(25.4) == pytest.approx(72.0)

    def test_conversions_round_trip(self):
        assert points_to_mm(mm_to_points(123.4)) == pytest.approx(123.4)


class TestParsePaper:
    @pytest.mark.parametrize("name", sorted(PAPER_SIZES_MM))
    def test_every_known_size_is_portrait(self, name):
        width, height = parse_paper(name)
        assert 0 < width <= height

    def test_names_are_case_insensitive(self):
        assert parse_paper("A4") == parse_paper("a4") == (210.0, 297.0)

    def test_custom_sizes(self):
        assert parse_paper("200x250") == (200.0, 250.0)
        assert parse_paper(" 250 X 200 ") == (200.0, 250.0)

    def test_custom_sizes_are_normalised_to_portrait(self):
        assert parse_paper("297x210") == (210.0, 297.0)

    @pytest.mark.parametrize("spec", ["a99", "", "20x", "x20", "big", "0x0"])
    def test_invalid_specifications_are_rejected(self, spec):
        with pytest.raises(ValueError):
            parse_paper(spec)


class TestLandscape:
    def test_turns_portrait_into_landscape(self):
        assert landscape((210.0, 297.0)) == (297.0, 210.0)

    def test_leaves_landscape_alone(self):
        assert landscape((297.0, 210.0)) == (297.0, 210.0)
