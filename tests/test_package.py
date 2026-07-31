"""Checks on the package itself, rather than on booklets."""

from __future__ import annotations

import subprocess
import sys

import pytest

import booklette


def test_the_public_api_is_importable():
    for name in booklette.__all__:
        assert hasattr(booklette, name), f"{name} is listed in __all__ but missing"


def test_the_version_matches_the_installed_distribution():
    metadata = pytest.importorskip("importlib.metadata")
    try:
        installed = metadata.version("booklette")
    except metadata.PackageNotFoundError:
        pytest.skip("package is not installed; run `pip install -e .`")
    assert installed == booklette.__version__


def test_the_module_can_be_run_as_a_script():
    result = subprocess.run(
        [sys.executable, "-m", "booklette", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert booklette.__version__ in result.stdout
