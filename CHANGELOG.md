# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-31

First release.

### Added

- Saddle-stitch imposition: two portrait pages per sheet side, ordered so that a
  duplex print folded in half reads correctly.
- `--duplex long|short` for printers that flip on either edge; long-edge
  flipping rotates the back of each sheet by 180 degrees.
- `--order reverse|normal` for printers that stack face up or face down.
- `--signature` for folding long documents in groups instead of one thick fold.
- `--paper` with the common ISO and US sizes, or a custom `WIDTHxHEIGHT` in mm.
- `--margin` and `--gutter` for whitespace at the edges and at the staple.
- `--rtl` for right-to-left booklets.
- `--dry-run` to print the imposition plan without writing a file.
- Support for encrypted inputs via `--password`, and for pages carrying a
  `/Rotate` flag.
- A Python API: `create_booklet`, `BookletOptions`, `impose`, `format_plan`.

[Unreleased]: https://github.com/nimjal/booklette/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nimjal/booklette/releases/tag/v0.1.0
