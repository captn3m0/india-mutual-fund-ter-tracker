from src import parse_ter

# TODO: Add test for generate_diff
class TestTer:
    def test_parser(self):
        with open("test/54.html") as f:
            html = f.read()
            data = parse_ter(html)
            assert len(data) == 78
