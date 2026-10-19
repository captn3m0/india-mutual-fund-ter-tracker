from datetime import date
from src import parse_ter, canonical_name, generate_diff, write_csv
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
