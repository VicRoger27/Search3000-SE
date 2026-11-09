"""Tests for Search3000 FastAPI Endpoints (api/main.py)."""

import unittest
from fastapi.testclient import TestClient

from api.main import app, spider, store


class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_serve_index(self):
        """Test root / serves HTML web interface."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Search3000", response.text)

    def test_get_index_stats(self):
        """Test /api/index/stats returns storage, spider, and model statistics."""
        response = self.client.get("/api/index/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("storage", data)
        self.assertIn("spider", data)
        self.assertIn("model", data)
        self.assertEqual(data["model"]["name"], "MiniCPM 5:2B")

    def test_get_spider_status(self):
        """Test /api/spider/status returns real-time crawler metrics."""
        response = self.client.get("/api/spider/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("spider", data)
        self.assertIn("storage", data)

    def test_toggle_spider(self):
        """Test /api/spider/toggle starts and stops the background spider."""
        initial_state = spider.is_running
        response = self.client.post("/api/spider/toggle")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["is_running"], not initial_state)

        # Toggle back to original state
        response_back = self.client.post("/api/spider/toggle")
        self.assertEqual(response_back.status_code, 200)
        self.assertEqual(response_back.json()["is_running"], initial_state)

    def test_search_empty_query(self):
        """Test /api/search with empty query returns zero results without crashing."""
        response = self.client.get("/api/search", params={"q": "   ", "skip_ai": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_results"], 0)
        self.assertEqual(data["results"], [])

    def test_search_with_query_skip_ai(self):
        """Test /api/search with standard query and skip_ai=True."""
        response = self.client.get("/api/search", params={"q": "quantum", "skip_ai": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["raw_query"], "quantum")
        self.assertIsInstance(data["results"], list)
        self.assertIn("time_ms", data)
        self.assertIn("stats", data)

    def test_search_sanitization_control_chars(self):
        """Test /api/search sanitizes null bytes and control chars from query."""
        response = self.client.get(
            "/api/search",
            params={"q": "quantum\x00\x1fsuperconductor", "skip_ai": True},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("\x00", data["raw_query"])
        self.assertNotIn("\x1f", data["raw_query"])
        self.assertIn("quantum", data["raw_query"])

    def test_search_filter_whitelist_fallback(self):
        """Test /api/search falls back to 'all' on an unrecognized filter_type."""
        response = self.client.get(
            "/api/search",
            params={"q": "quantum", "skip_ai": True, "filter_type": "malicious_filter"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data["results"], list)

    def test_search_max_length_validation(self):
        """Test /api/search rejects queries exceeding 300 characters with HTTP 422."""
        long_q = "a" * 301
        response = self.client.get("/api/search", params={"q": long_q, "skip_ai": True})
        self.assertEqual(response.status_code, 422)

    def test_page_reader_and_view_endpoints(self):
        """Test /page/{doc_id} and /api/page/view/{doc_id} render cached Base128 pages."""
        # Index a sample document to test reader view
        test_doc_id = store.add_document(
            url="https://en.wikipedia.org/wiki/Unit_Test_Sample",
            title="Unit Test Sample Page",
            content="This is sample content for testing the in-engine reader view.",
            source="unit_test",
        )
        # Test JSON endpoint
        res_json = self.client.get(f"/api/page/view/{test_doc_id}")
        self.assertEqual(res_json.status_code, 200)
        self.assertEqual(res_json.json()["doc"]["title"], "Unit Test Sample Page")

        # Test HTML reader endpoint
        res_html = self.client.get(f"/page/{test_doc_id}")
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("text/html", res_html.headers.get("content-type", ""))
        self.assertIn("Unit Test Sample Page", res_html.text)
        self.assertIn("Base128 Reader", res_html.text)

    def test_ai_stream_endpoint(self):
        """Test /api/ai/stream streams SSE chunks terminating in [DONE]."""
        with self.client.stream("GET", "/api/ai/stream", params={"q": "quantum computing"}) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers.get("content-type", ""))
            body = "".join(response.iter_text())
            self.assertIn("data: [DONE]", body)


if __name__ == "__main__":
    unittest.main()
