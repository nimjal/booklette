"""Where on the sheet each page goes.

Like :mod:`booklette.imposition`, this module is pure arithmetic with no
PDF library involved, so the geometry can be unit-tested on its own.

The sheet is used in landscape and split down the middle by the fold::

    +---------------------+---------------------+  <- sheet, e.g. A4 landscape
    |                     |                     |
    |     left slot       |     right slot      |
    |                     |                     |
    +---------------------+---------------------+
                          ^ fold

``margin`` is whitespace kept at the three outer edges of each slot, ``gutter``
is whitespace kept at the fold. Both shrink the area a page is scaled into; the
page itself is never cropped.
"""

from __future__ import annotations

from dataclasses import dataclass

from .paper import landscape, mm_to_points

#: A PDF transformation matrix ``(a, b, c, d, e, f)``, which maps a point to
#: ``(a*x + c*y + e, b*x + d*y + f)``.
Matrix = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in PDF points, anchored at its lower-left corner."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class SheetLayout:
    """The printable geometry of one sheet, in PDF points."""

    width: float
    height: float
    left_slot: Rect
    right_slot: Rect

    def slot(self, *, is_right: bool) -> Rect:
        """Return the left or right slot."""
        return self.right_slot if is_right else self.left_slot


#: Clockwise rotations by a multiple of 90 degrees, as the ``(a, b, c, d)`` part
#: of a PDF matrix. Written out rather than computed with sine and cosine so the
#: numbers stay exact.
_ROTATION_MATRICES: dict[int, tuple[float, float, float, float]] = {
    0: (1.0, 0.0, 0.0, 1.0),
    90: (0.0, -1.0, 1.0, 0.0),
    180: (-1.0, 0.0, 0.0, -1.0),
    270: (0.0, 1.0, -1.0, 0.0),
}


def rotation_matrix(degrees: int) -> tuple[float, float, float, float]:
    """The ``(a, b, c, d)`` matrix for a clockwise rotation of ``degrees``.

    :raises ValueError: unless ``degrees`` is a multiple of 90.
    """
    normalised = int(degrees) % 360
    if normalised not in _ROTATION_MATRICES:
        raise ValueError(f"Only quarter turns are supported, got {degrees} degrees")
    return _ROTATION_MATRICES[normalised]


def rotate_point(x: float, y: float, degrees: int) -> tuple[float, float]:
    """Rotate a point clockwise around the origin by a multiple of 90 degrees."""
    a, b, c, d = rotation_matrix(degrees)
    return (a * x + c * y, b * x + d * y)


@dataclass(frozen=True)
class Placement:
    """Instructions for putting one source page into one slot.

    Applied in this order, which is also the order the PDF transformation is
    built in:

    1. rotate clockwise by ``source_rotation`` - PDF pages can carry a
       ``/Rotate`` flag that viewers apply on display, and the sheet has to show
       what the viewer shows,
    2. translate by ``source_offset``, which lands the page's lower-left corner
       on the origin (a page's box does not have to start at ``0, 0``),
    3. scale by ``scale``,
    4. rotate by 180 degrees if ``rotate_180``,
    5. translate by ``translate`` to land on the sheet.
    """

    source_rotation: int
    source_offset: tuple[float, float]
    scale: float
    rotate_180: bool
    translate: tuple[float, float]

    def matrix(self) -> Matrix:
        """The five steps combined into a single PDF transformation matrix.

        >>> Placement(0, (0.0, 0.0), 0.5, False, (10.0, 20.0)).matrix()
        (0.5, 0.0, 0.0, 0.5, 10.0, 20.0)
        """
        combined = _rotation(self.source_rotation)
        combined = multiply(combined, _translation(*self.source_offset))
        combined = multiply(combined, _scaling(self.scale))
        if self.rotate_180:
            combined = multiply(combined, _rotation(180))
        return multiply(combined, _translation(*self.translate))

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """Map a point of the source page onto the sheet. Useful for testing."""
        a, b, c, d, e, f = self.matrix()
        return (a * x + c * y + e, b * x + d * y + f)


def multiply(first: Matrix, second: Matrix) -> Matrix:
    """Combine two PDF matrices: ``first`` applied, then ``second``.

    PDF treats coordinates as row vectors, so combining transformations is a
    plain matrix product with the operations read left to right.
    """
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _rotation(degrees: int) -> Matrix:
    """A clockwise quarter turn around the origin."""
    a, b, c, d = rotation_matrix(degrees)
    return (a, b, c, d, 0.0, 0.0)


def _translation(x: float, y: float) -> Matrix:
    return (1.0, 0.0, 0.0, 1.0, float(x), float(y))


def _scaling(factor: float) -> Matrix:
    return (float(factor), 0.0, 0.0, float(factor), 0.0, 0.0)


def build_sheet_layout(
    paper_mm: tuple[float, float],
    *,
    margin_mm: float = 0.0,
    gutter_mm: float = 0.0,
) -> SheetLayout:
    """Compute the two page slots for a sheet of ``paper_mm`` used in landscape.

    :param paper_mm: portrait ``(width, height)`` of the paper, in millimetres.
    :param margin_mm: whitespace at the outer edges of the sheet.
    :param gutter_mm: extra whitespace either side of the fold, for binding.

    >>> layout = build_sheet_layout((210.0, 297.0))
    >>> round(layout.width, 2), round(layout.height, 2)
    (841.89, 595.28)
    >>> round(layout.right_slot.x, 2)
    420.94
    """
    if margin_mm < 0 or gutter_mm < 0:
        raise ValueError("margin and gutter cannot be negative")

    sheet_width_mm, sheet_height_mm = landscape(paper_mm)
    width = mm_to_points(sheet_width_mm)
    height = mm_to_points(sheet_height_mm)
    margin = mm_to_points(margin_mm)
    gutter = mm_to_points(gutter_mm)

    fold = width / 2.0
    slot_width = fold - margin - gutter
    slot_height = height - 2 * margin
    if slot_width <= 0 or slot_height <= 0:
        raise ValueError("margin and gutter leave no room for the pages")

    return SheetLayout(
        width=width,
        height=height,
        # The gutter is always on the side facing the fold.
        left_slot=Rect(x=margin, y=margin, width=slot_width, height=slot_height),
        right_slot=Rect(x=fold + gutter, y=margin, width=slot_width, height=slot_height),
    )


def visible_size(source: Rect, rotation: int) -> tuple[float, float]:
    """The ``(width, height)`` of ``source`` as displayed, i.e. after ``rotation``.

    >>> visible_size(Rect(0, 0, 100, 200), 0)
    (100.0, 200.0)
    >>> visible_size(Rect(0, 0, 100, 200), 90)
    (200.0, 100.0)
    """
    if rotation_matrix(rotation)[0] == 0:  # a quarter turn: width and height swap
        return (float(source.height), float(source.width))
    return (float(source.width), float(source.height))


def normalise_offset(source: Rect, rotation: int) -> tuple[float, float]:
    """The shift that puts ``source``, once rotated, back onto the origin.

    >>> normalise_offset(Rect(10, 20, 100, 200), 0)
    (-10.0, -20.0)
    """
    corners = [
        rotate_point(x, y, rotation)
        for x in (source.x, source.right)
        for y in (source.y, source.top)
    ]
    return (-min(x for x, _ in corners), -min(y for _, y in corners))


def place(
    source: Rect,
    slot: Rect,
    layout: SheetLayout,
    *,
    upside_down: bool,
    source_rotation: int = 0,
) -> Placement:
    """Fit ``source`` into ``slot``, centred, keeping its aspect ratio.

    ``source_rotation`` is the page's own ``/Rotate`` flag: a quarter turn there
    swaps the width and the height that the slot has to accommodate.

    When ``upside_down`` is set the placement is additionally point-mirrored
    through the centre of the sheet. That is what turns a normal sheet side into
    one that survives long-edge duplex: both halves swap sides *and* flip, which
    is exactly what happens to the paper itself.
    """
    if source.width <= 0 or source.height <= 0:
        raise ValueError("Source page has no area")

    visible_width, visible_height = visible_size(source, source_rotation)
    scale = min(slot.width / visible_width, slot.height / visible_height)
    scaled_width = visible_width * scale
    scaled_height = visible_height * scale

    # Centre the scaled page inside its slot.
    x = slot.x + (slot.width - scaled_width) / 2.0
    y = slot.y + (slot.height - scaled_height) / 2.0

    # After rotating 180 degrees the page occupies negative coordinates, so
    # translating by the *opposite* corner of the sheet puts it back where it
    # belongs, mirrored through the centre of the sheet.
    translate = (layout.width - x, layout.height - y) if upside_down else (x, y)

    return Placement(
        source_rotation=int(source_rotation) % 360,
        source_offset=normalise_offset(source, source_rotation),
        scale=scale,
        rotate_180=upside_down,
        translate=translate,
    )
