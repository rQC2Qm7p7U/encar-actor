import unittest
from pathlib import Path

from parser import EncarParseError, extract_preloaded_state, parse_vehicle, validate_state


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_HTML = ROOT / "sample.html"


class ParserTests(unittest.TestCase):
    def test_extract_preloaded_state_with_sample_html(self) -> None:
        html = SAMPLE_HTML.read_text(encoding="utf-8")
        state = extract_preloaded_state(html)
        # Basic structure guards to detect breaking layout changes.
        self.assertIn("cars", state)
        self.assertIn("base", state.get("cars", {}))
        self.assertIn("advertisement", state.get("cars", {}).get("base", {}))

    def test_parse_vehicle_from_sample_html(self) -> None:
        result = parse_vehicle("40849700", html_path=str(SAMPLE_HTML))
        self.assertIn("data", result)
        data = result["data"]
        self.assertTrue(data.get("id"))
        self.assertTrue(data.get("url", "").endswith("/40849700"))
        self.assertIn("price", data)
        self.assertIn("mileage", data)

    def test_extract_preloaded_state_missing_marker(self) -> None:
        html = "<html><body><script>console.log('no state here');</script></body></html>"
        with self.assertRaises(EncarParseError):
            extract_preloaded_state(html)

    def test_extract_preloaded_state_malformed_json(self) -> None:
        html = "<script>__PRELOADED_STATE__ = {bad-json}</script>"
        with self.assertRaises(EncarParseError):
            extract_preloaded_state(html)

    def test_validate_state_missing_base(self) -> None:
        with self.assertRaises(EncarParseError):
            validate_state({})

    def test_validate_state_incomplete_base(self) -> None:
        state = {"cars": {"base": {}}}
        with self.assertRaises(EncarParseError):
            validate_state(state)


if __name__ == "__main__":
    unittest.main()
