"""Tests for the command line interface."""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from booklette.cli import main
from booklette.filler import Filler
from booklette.imposition import Duplex, SheetOrder


class TestDefaults:
    def test_writes_next_to_the_input_by_default(self, numbered_pdf, capsys):
        source = numbered_pdf(8)

        assert main([str(source)]) == 0

        output = source.with_name("source-booklet.pdf")
        assert output.exists()
        assert len(PdfReader(output).pages) == 4
        assert "Wrote" in capsys.readouterr().out

    def test_explicit_output_path(self, numbered_pdf, tmp_path):
        source = numbered_pdf(4)
        target = tmp_path / "nested" / "out.pdf"
        target.parent.mkdir()

        assert main([str(source), "-o", str(target)]) == 0
        assert target.exists()

    def test_quiet_prints_nothing(self, numbered_pdf, capsys):
        main([str(numbered_pdf(4)), "--quiet"])
        assert capsys.readouterr().out == ""

    def test_summary_mentions_padding(self, numbered_pdf, capsys):
        main([str(numbered_pdf(5))])

        out = capsys.readouterr().out
        assert "3 padding page(s) added" in out
        assert "2 with notes" in out
        assert "1 left blank" in out  # the back cover

    def test_summary_of_an_unfilled_booklet(self, numbered_pdf, capsys):
        main([str(numbered_pdf(5)), "--filler", "blank"])
        assert "3 left blank" in capsys.readouterr().out


class TestOptions:
    def test_parses_the_printing_options(self):
        from booklette.cli import build_parser

        args = build_parser().parse_args(
            ["in.pdf", "--duplex", "short", "--order", "reverse", "--signature", "16"]
        )

        assert args.duplex is Duplex.SHORT_EDGE
        assert args.order is SheetOrder.REVERSE
        assert args.signature == 16

    def test_printing_defaults(self):
        from booklette.cli import build_parser

        args = build_parser().parse_args(["in.pdf"])

        assert args.order is SheetOrder.NORMAL
        assert args.duplex is Duplex.LONG_EDGE
        assert args.filler is Filler.NOTES
        assert args.filler_title == "Notes:"
        assert args.filler_back_cover is False

    def test_parses_the_filler_options(self):
        from booklette.cli import build_parser

        args = build_parser().parse_args(
            ["in.pdf", "--filler", "lines", "--filler-title", "Ideas", "--filler-back-cover"]
        )

        assert args.filler is Filler.LINES
        assert args.filler_title == "Ideas"
        assert args.filler_back_cover is True

    def test_filler_changes_the_output(self, numbered_pdf, tmp_path):
        source = numbered_pdf(5)
        main([str(source), "-o", str(tmp_path / "notes.pdf")])
        main([str(source), "-o", str(tmp_path / "blank.pdf"), "--filler", "blank"])

        assert (tmp_path / "notes.pdf").read_bytes() != (tmp_path / "blank.pdf").read_bytes()

    def test_margin_and_gutter_change_the_output(self, numbered_pdf, tmp_path):
        source = numbered_pdf(4)
        main([str(source), "-o", str(tmp_path / "a.pdf")])
        main([str(source), "-o", str(tmp_path / "b.pdf"), "-m", "10", "-g", "5"])

        assert (tmp_path / "a.pdf").read_bytes() != (tmp_path / "b.pdf").read_bytes()

    def test_dry_run_writes_no_file(self, numbered_pdf, capsys):
        source = numbered_pdf(8)

        assert main([str(source), "--dry-run"]) == 0

        assert not source.with_name("source-booklet.pdf").exists()
        assert "sheet 1/2" in capsys.readouterr().out

    def test_version(self, capsys):
        from booklette import __version__

        with pytest.raises(SystemExit) as exit_info:
            main(["--version"])

        assert exit_info.value.code == 0
        assert __version__ in capsys.readouterr().out


class TestErrors:
    def test_missing_input_file(self, tmp_path, capsys):
        assert main([str(tmp_path / "nope.pdf")]) == 1
        assert "error:" in capsys.readouterr().err

    def test_bad_paper_size(self, numbered_pdf, capsys):
        assert main([str(numbered_pdf(4)), "--paper", "a99"]) == 1
        assert "Unknown paper size" in capsys.readouterr().err

    def test_bad_signature_size(self, numbered_pdf, capsys):
        assert main([str(numbered_pdf(12)), "--signature", "6"]) == 1
        assert "multiple of 4" in capsys.readouterr().err

    def test_unknown_flag_exits_with_usage(self):
        with pytest.raises(SystemExit) as exit_info:
            main(["in.pdf", "--nope"])
        assert exit_info.value.code == 2
