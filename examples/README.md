# Examples

Runnable scripts. From the root of the repository, with the package installed
(`pip install -e .`):

## `make_sample_pdf.py`

Writes a numbered test document using nothing but the standard library. Every
page carries a large page number, a "TOP" bar along the top edge and a frame, so
that a printed and folded copy immediately shows whether the order and the
orientation are right.

```bash
python examples/make_sample_pdf.py sample.pdf --pages 12
booklette sample.pdf
```

Print `sample-booklet.pdf` double-sided, fold it, and read the numbers: if they
run 1, 2, 3 ... and every "TOP" bar is at the top, your printer agrees with the
default options.

The test suite imports this script as a fixture, so it stays working.

## `basic_usage.py`

The library API. Creates a sample document and imposes it three ways - defaults,
generous margins, and short-edge duplex with signatures - into `examples/output/`.

```bash
python examples/basic_usage.py
```

## `print_plan.py`

The page ordering on its own, with no PDFs involved. Useful for checking by hand
which page ends up where, and for seeing what `--signature`, `--order` and
`--duplex` actually change.

```bash
python examples/print_plan.py
```
