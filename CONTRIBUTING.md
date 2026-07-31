# Contributing

Thanks for taking the time. Bug reports, printer quirks and pull requests are
all welcome.

## Getting set up

```bash
git clone https://github.com/nimjal/booklette.git
cd booklette
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

`pytest` runs the unit tests, the end-to-end tests and the doctests in the
source files. Everything should pass in under a couple of seconds; if it does
not, that is a bug in itself.

## Before you open a pull request

```bash
ruff format .     # formatting
ruff check .      # linting
pytest            # tests
```

CI runs the same three commands on Linux, macOS and Windows across the supported
Python versions.

## House style

The point of this project is that someone can read it and understand how
booklet imposition works. Clarity beats cleverness:

- keep the three layers separate - page ordering (`imposition.py`), geometry
  (`layout.py`) and PDF handling (`builder.py`). The first two must stay free of
  any PDF library so they can be tested on their own.
- explain *why* in comments, especially anything to do with paper, folding and
  duplex flipping. Those parts are hard to re-derive later.
- add a test for behaviour you change. If it involves geometry, prefer a test
  against `layout.py` over one that has to open a PDF.
- type hints on public functions, docstrings on anything a user might call.

## Reporting a printing problem

Booklet output depends on how a specific printer feeds and flips paper, so
please include:

- the exact command you ran,
- your printer and the duplex setting you used,
- what came out: wrong page order, upside-down backs, mirrored halves...

A photo of the folded result says more than a paragraph. If your printer needs a
combination of options that is not currently possible, say so - that is a
feature request, not a mistake on your side.

## Releases

Maintainer checklist:

1. update `CHANGELOG.md`,
2. bump the version in `pyproject.toml` and `src/booklette/__init__.py`,
3. tag the commit `vX.Y.Z` and push the tag - the publish workflow builds the
   distribution and uploads it to PyPI.
