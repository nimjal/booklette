"""Paper sizes and unit conversions.

PDF measures everything in *points*: 1 point = 1/72 inch. Humans (and printer
dialogs) mostly think in millimetres, so every public option in this package is
expressed in millimetres and converted here, in exactly one place.
"""

from __future__ import annotations

import re

#: A PostScript point is 1/72 inch, and one inch is 25.4 mm.
POINTS_PER_MM = 72.0 / 25.4

#: Known paper sizes, in millimetres, always given as (width, height) *portrait*.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "a6": (105.0, 148.0),
    "b5": (176.0, 250.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
    "tabloid": (279.4, 431.8),
}

#: Matches a custom size such as "210x297", "210 x 297" or "216.0X279.4".
_CUSTOM_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)


def mm_to_points(millimetres: float) -> float:
    """Convert millimetres to PDF points."""
    return millimetres * POINTS_PER_MM


def points_to_mm(points: float) -> float:
    """Convert PDF points to millimetres."""
    return points / POINTS_PER_MM


def parse_paper(spec: str) -> tuple[float, float]:
    """Resolve a paper specification to a portrait ``(width, height)`` in mm.

    Accepts either a name from :data:`PAPER_SIZES_MM` (case-insensitive, so
    ``"A4"`` and ``"a4"`` both work) or a custom ``WIDTHxHEIGHT`` string in
    millimetres, for example ``"200x250"``.

    >>> parse_paper("A4")
    (210.0, 297.0)
    >>> parse_paper("250x200")
    (200.0, 250.0)

    :raises ValueError: if the specification cannot be understood.
    """
    key = spec.strip().lower()
    if key in PAPER_SIZES_MM:
        return PAPER_SIZES_MM[key]

    match = _CUSTOM_SIZE.match(spec)
    if match:
        width, height = float(match.group(1)), float(match.group(2))
        if width <= 0 or height <= 0:
            raise ValueError(f"Paper dimensions must be positive: {spec!r}")
        # Normalise to portrait so callers can rely on height >= width.
        return (min(width, height), max(width, height))

    known = ", ".join(sorted(PAPER_SIZES_MM))
    raise ValueError(f"Unknown paper size {spec!r}. Use one of: {known} - or 'WIDTHxHEIGHT' in mm.")


def landscape(size_mm: tuple[float, float]) -> tuple[float, float]:
    """Return ``size_mm`` rotated to landscape, i.e. ``(long side, short side)``.

    A booklet sheet always holds two portrait pages side by side, so the sheet
    itself is used in landscape.

    >>> landscape((210.0, 297.0))
    (297.0, 210.0)
    """
    width, height = size_mm
    return (max(width, height), min(width, height))
