from src import parse_ter,canonical_name

# TODO: Add test for generate_diff
class TestTer:
    def test_parser(self):
        with open("test/54.html") as f:
            html = f.read()
            data = parse_ter(html)
            assert len(data) == 78


    def test_scheme_name(self):
        assert canonical_name("BANDHAN Multi Cap Fund") == "Bandhan Multi Cap Fund"
        assert canonical_name("Bandhan Tax Advantage (ELSS) Fund") == "Bandhan Tax Advantage (ELSS) Fund"
        assert canonical_name("dsp nifty 1d rate liquid etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("DSP NIFTY 1D RATE LIQUID ETF") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("Dsp Nifty 1d Rate Liquid Etf") == "DSP Nifty 1D Rate Liquid ETF"
        assert canonical_name("LIC MF Children'S Gift Fund") == "LIC MF Children's Gift Fund"