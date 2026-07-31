# booklette

[![CI](https://github.com/nimjal/booklette/actions/workflows/ci.yml/badge.svg)](https://github.com/nimjal/booklette/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Turn an ordinary page-by-page PDF into one you can print, fold and staple into a
booklet.

Each sheet of the output holds **two portrait pages side by side**, with the page
numbers shuffled into the order a folded booklet needs. Print it double-sided on
A4, fold the stack in half, staple the fold - you have an A5 booklet that reads
from page 1 to the end.

```
input.pdf                        booklet.pdf (A4 landscape, 2-up)
+-----+ +-----+ +-----+          +-----+-----+   +-----+-----+
|  1  | |  2  | |  3  |   --->   |  8  |  1  |   |  2  |  7  |  ...
+-----+ +-----+ +-----+          +-----+-----+   +-----+-----+
   ...  8 pages  ...              sheet 1 front   sheet 1 back
```

(The back sides are additionally turned 180 degrees, which is what makes
long-edge duplex printing come out right - see [Printing](#printing).)

## Install

```bash
pip install booklette
```

Or from a clone of this repository:

```bash
git clone https://github.com/nimjal/booklette.git
cd booklette
pip install -e .
```

The only runtime dependency is [pypdf](https://pypdf.readthedocs.io/).

## Usage

```bash
# The common case: A4 booklet with the defaults described below
booklette report.pdf                 # writes report-booklet.pdf

# A little breathing room around the pages and at the staple
booklette report.pdf --margin 8 --gutter 4

# A long document, folded in groups of 16 pages instead of one thick fold
booklette novel.pdf --signature 16

# See where every page will end up, without writing a file
booklette report.pdf --dry-run
```

Or from Python:

```python
from booklette import BookletOptions, create_booklet

result = create_booklet("report.pdf", "booklet.pdf", BookletOptions(margin_mm=8))
print(f"{result.source_pages} pages -> {result.sheets} sheets")
```

## Printing

1. Print the generated PDF **double-sided (duplex)**.
2. Set scaling to **100% / "actual size"** - not "fit to page", which would
   shrink the pages a second time.
3. Fold the stack in half and staple the fold.

Two printer habits decide the settings, and both are options:

| Option | Default | Change it when |
| --- | --- | --- |
| `--duplex long` / `short` | `long` | the back of each sheet comes out upside down |
| `--order reverse` / `normal` | `reverse` | the finished stack is back to front |

**`--duplex`** describes how the printer turns the paper between the two sides.
Because the sheets are landscape but the paper is fed portrait, long-edge
flipping needs the back of every sheet rotated by 180 degrees - that rotation is
baked into the output, so the printer dialog stays on its own default. Pick
`short` if your driver flips on the short edge instead.

> **Every second page of the output looks upside down on screen. That is
> correct.** It is the long-edge correction, and it comes out the right way up
> on paper. If you would rather preview an output that reads upright, use
> `--duplex short` and set your printer to flip on the short edge.

**`--order`** describes how the printer stacks its output. Printers that drop
pages face up build the pile "bottom to top", so the last page printed ends up
on top; emitting the sheets last-first (the default, `reverse`) makes the
finished pile come out in the right order. Use `normal` for printers that stack
face down.

If a test print comes out wrong, change **one** of the two and try again - four
pages of scrap paper will tell you which combination your printer wants.

## Options

| Flag | Default | What it does |
| --- | --- | --- |
| `-o, --output PATH` | `<input>-booklet.pdf` | where to write the result |
| `-p, --paper SIZE` | `a4` | `a3`, `a4`, `a5`, `a6`, `b5`, `letter`, `legal`, `tabloid`, or `WIDTHxHEIGHT` in mm |
| `-d, --duplex {long,short}` | `long` | edge the printer flips on |
| `--order {reverse,normal}` | `reverse` | sheet output order |
| `-s, --signature PAGES` | `0` | fold in groups of PAGES pages (multiple of 4); `0` folds everything at once |
| `-m, --margin MM` | `0` | whitespace at the outer edges of the sheet |
| `-g, --gutter MM` | `0` | extra whitespace either side of the fold |
| `--rtl` | off | right-to-left booklet (spine on the right) |
| `--password PASS` | - | password for an encrypted input PDF |
| `-n, --dry-run` | off | print the imposition plan, write nothing |
| `-q, --quiet` | off | only report errors |

Pages are scaled to fit their half of the sheet and centred, keeping their
aspect ratio; a document of mixed page sizes is handled page by page. The page
count is padded with blanks up to a multiple of four, because that is how many
pages one folded sheet carries.

### Signatures

One fold through more than about ten sheets bulges badly and the inner pages
stick out. `--signature 16` instead produces a series of small booklets (four
sheets each) that you fold separately and then stack in order - the way real
books are bound.

## How it works

A saddle-stitched booklet of `n` pages puts these pages on sheet `i`
(counting from 0):

| sheet side | left half | right half |
| --- | --- | --- |
| front | `n - 2i` | `2i + 1` |
| back | `2i + 2` | `n - 2i - 1` |

So an 8 page booklet becomes `[8|1] [2|7] [6|3] [4|5]`. The code follows the
same three steps:

| Module | Responsibility |
| --- | --- |
| `imposition.py` | which page goes where - pure Python, no PDF library |
| `layout.py` | where on the sheet it goes - rectangles and matrices, no PDF library |
| `builder.py` | the only module that talks to pypdf |
| `cli.py` | the command line |

Because the first two modules are pure arithmetic, the tricky parts are covered
by fast unit tests, and you can inspect the plan without a PDF at all:

```python
from booklette import format_plan, impose

print(format_plan(impose(12)))
```

## Examples

The [`examples/`](examples) directory has runnable scripts, including a sample
PDF generator that uses nothing but the standard library:

```bash
python examples/make_sample_pdf.py sample.pdf --pages 12
booklette sample.pdf
python examples/basic_usage.py     # library API, three variations
python examples/print_plan.py      # page ordering, no PDFs involved
```

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip
pytest                              # unit tests, end-to-end tests and doctests
ruff check .
ruff format .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to send a change.

## Limitations

- Two pages per sheet, folded down the middle: no 4-up, no cut-and-stack, no
  creep compensation for very thick booklets.
- The output is a normal PDF; the actual printing is left to your printer
  dialog, which is where the paper handling settings live anyway.

## License

MIT - see [LICENSE](LICENSE).
