from src import parse_ter,canonical_name
import gzip


# TODO: Add test for generate_diff
class TestTer:

    def test_large_parser(self):
        with gzip.open("test/large.html.gz") as f:
            rows = parse_ter(f.read())
            assert len(rows) == 1447

    def test_scheme_name(self):
        assert canonical_name("BANDHAN Multi Cap Fund") == "Bandhan Multi Cap Fund"
        assert canonical_name("Bandhan Tax Advantage (ELSS) Fund") == "Bandhan Tax Advantage (ELSS) Fund"
        assert canonical_name("dsp nifty 1d rate liquid etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("DSP NIFTY 1D RATE LIQUID ETF") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("Dsp Nifty 1d Rate Liquid Etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("LIC MF Children'S Gift Fund") == "LIC MF Children's Gift Fund"