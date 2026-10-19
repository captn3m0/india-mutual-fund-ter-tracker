from datetime import date, datetime
from src import parse_ter, read_ter_rows, canonical_name, generate_diff, write_csv, check_row_count
from src.feed import parse_log
import io
import openpyxl
import pytest


class TestTer:

    def test_parser(self):
        with open("test/ter.xlsx", "rb") as f:
            rows = parse_ter(read_ter_rows(f.read()))
        assert len(rows) == 3
        fund = rows["360 One Balanced Hybrid Fund"]
        assert fund[0] == date(2026, 10, 18)
        assert fund[2:] == [1.78, 0.03, 0.0, 0.38, 2.19, 0.49, 0.03, 0.0, 0.15, 0.67]
        assert rows["360 One Quant Fund"][-1] == 1.11

    def test_parser_merges_case_variants(self):
        values = [0.0] * 10
        rows = parse_ter([
            ["TATA GILT FUND", datetime(2026, 9, 30)] + values[:-1] + [0.3],
            ["Tata Gilt Fund", datetime(2026, 10, 1)] + values[:-1] + [0.25],
        ])
        assert list(rows) == ["Tata Gilt Fund"]
        assert rows["Tata Gilt Fund"][-1] == 0.25

    def test_missing_columns(self):
        book = openpyxl.Workbook()
        book.active.append(["Scheme Name", "TER Date", "Direct Plan - GST (%)"])
        out = io.BytesIO()
        book.save(out)
        with pytest.raises(ValueError, match="Columns missing"):
            list(read_ter_rows(out.getvalue()))

    def test_generate_diff(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        regular = [1.0, 0.0, 0.0, 0.18, 1.18]
        write_csv(old, [["A Fund"] + regular + [0.5, 0.0, 0.0, 0.1, 0.6], ["B Fund"] + regular * 2])
        write_csv(new, [["A Fund"] + regular + [0.4, 0.0, 0.0, 0.1, 0.5], ["B Fund"] + regular[:4] + [1.25] + regular])
        out = io.StringIO()
        generate_diff(old, new, out)
        assert out.getvalue() == '- "A Fund" lowered its TER from 0.6 to 0.5\n'

    def test_check_row_count(self, tmp_path):
        old = tmp_path / "old.csv"
        write_csv(old, [[f"Fund {i}"] + [0.0] * 10 for i in range(10)])
        check_row_count(old, [[]] * 9)
        check_row_count(tmp_path / "missing.csv", [])
        with pytest.raises(ValueError, match="dropped from 10 to 8"):
            check_row_count(old, [[]] * 8)

    def test_scheme_name(self):
        assert canonical_name("BANDHAN Multi Cap Fund") == "Bandhan Multi Cap Fund"
        assert canonical_name("Bandhan Tax Advantage (ELSS) Fund") == "Bandhan Tax Advantage (ELSS) Fund"
        assert canonical_name("dsp nifty 1d rate liquid etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("DSP NIFTY 1D RATE LIQUID ETF") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("Dsp Nifty 1d Rate Liquid Etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("LIC MF Children'S Gift Fund") == "LIC MF Children's Gift Fund"


class TestFeed:

    def test_parse_log(self):
        log = (
            "abc\x002026-10-19T10:35:00+05:30\x00tag: v2.2026292.10\x00Update Total Expense Ratios\n\n"
            "Changes in TER (Direct Plans):\n\n"
            '- "Fund \\"A\\"" lowered its TER from 0.6 to 0.5\n'
            '- "Fund B" increased its TER from 1.0 to 1.25\n\x1e\n'
            "def\x002026-10-19T09:35:00+05:30\x00\x00Update Total Expense Ratios\n\x1e\n"
        )
        entries = list(parse_log(log))
        assert len(entries) == 1
        assert entries[0]["url"].endswith("/releases/tag/v2.2026292.10")
        assert entries[0]["changes"] == [
            {"scheme": 'Fund \\"A\\"', "old": "0.6", "new": "0.5", "direction": "lowered"},
            {"scheme": "Fund B", "old": "1.0", "new": "1.25", "direction": "increased"},
        ]
