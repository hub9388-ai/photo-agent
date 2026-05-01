import json
import unittest
from unittest.mock import patch

import photo_provider_adapter


class FakeResponse:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> bytes:
        return self._text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ProviderAdapterTests(unittest.TestCase):
    def test_search_reference_links_parses_html_results(self) -> None:
        html_text = """
        <html><body>
        <a class="result__a" href="https://example.com/a">Sample A</a>
        <a class="result__a" href="https://example.com/b">Sample B</a>
        </body></html>
        """
        with patch("photo_provider_adapter.urlopen", return_value=FakeResponse(html_text)):
            results = photo_provider_adapter.search_reference_links("rainy street", limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Sample A")
        self.assertEqual(results[1]["url"], "https://example.com/b")

    def test_search_places_normalizes_amap_payload(self) -> None:
        payload = {
            "status": "1",
            "pois": [
                {
                    "id": "poi_1",
                    "name": "断桥残雪",
                    "location": "120.150,30.260",
                    "pname": "浙江省",
                    "cityname": "杭州市",
                    "adname": "西湖区",
                    "address": "北山街",
                    "type": "风景名胜;景点",
                    "biz_ext": {"rating": "4.9"},
                    "photos": [{"url": "https://example.com/dbcx.jpg"}],
                }
            ],
        }
        with patch("photo_provider_adapter.resolve_env_value", return_value="amap-key"):
            with patch("photo_provider_adapter.http_get_json", return_value=payload):
                results = photo_provider_adapter.search_places({"city": "杭州", "place_search_queries": ["杭州 西湖"]}, limit=3)

        self.assertEqual(results["status"], "ok")
        self.assertEqual(results["results"][0]["name"], "断桥残雪")
        self.assertEqual(results["results"][0]["rating"], "4.9")
        self.assertEqual(results["results"][0]["lat"], 30.26)


if __name__ == "__main__":
    unittest.main()

