from datetime import date
from src import parse_ter, canonical_name, generate_diff, write_csv
from src.feed import parse_log
import io
import json


class TestTer:

    def test_parser(self):
        with open("test/ter.json") as f:
            rows = parse_ter(json.load(f)["data"])
        assert len(rows) == 2
        hdfc = rows["HDFC FLEXI CAP FUND"]
        assert hdfc[0] == date(2026, 5, 20)
        assert hdfc[2:] == [1.09, 0.02, 0.0, 0.18, 1.35, 0.53, 0.02, 0.0, 0.21, 0.76]
        assert rows["Parag Parikh Flexi Cap Fund"][-3] == 0.0

    def test_generate_diff(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        regular = [1.0, 0.0, 0.0, 0.18, 1.18]
        write_csv(old, [["A Fund"] + regular + [0.5, 0.0, 0.0, 0.1, 0.6], ["B Fund"] + regular * 2])
        write_csv(new, [["A Fund"] + regular + [0.4, 0.0, 0.0, 0.1, 0.5], ["B Fund"] + regular[:4] + [1.25] + regular])
        out = io.StringIO()
        generate_diff(old, new, out)
        assert out.getvalue() == '- "A Fund" lowered its TER from 0.6 to 0.5\n'

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
