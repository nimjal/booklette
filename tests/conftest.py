"""Shared test fixtures.

The sample-PDF generator lives in ``examples/`` so that it doubles as a usage
example; the tests import it from there, which also keeps the example honest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
sys.path.insert(0, str(EXAMPLES_DIR))

from make_sample_pdf import make_numbered_pdf  # noqa: E402  (needs the path above)


@pytest.fixture
def numbered_pdf(tmp_path):
    """Return a factory that writes a numbered PDF into the test's temp dir."""

    def factory(page_count: int = 12, name: str = "source.pdf", **kwargs) -> Path:
        return make_numbered_pdf(tmp_path / name, page_count=page_count, **kwargs)

    return factory
