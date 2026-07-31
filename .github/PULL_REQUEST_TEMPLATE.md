# What does this change?

<!-- One or two sentences. Link the issue it closes, if there is one. -->

Closes #

## Why?

<!-- What was wrong, or what was missing? -->

## How was it tested?

- [ ] `pytest` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] Added or updated tests for the change

If the change affects the printed result, please also say:

- Printer and duplex setting used:
- Options passed to `booklette`:
- What the folded result looked like:

## Checklist

- [ ] The page ordering (`imposition.py`) and geometry (`layout.py`) modules are
      still free of any PDF library
- [ ] Comments explain anything non-obvious about paper, folding or duplex
- [ ] `README.md` and `CHANGELOG.md` updated if the behaviour or options changed
