import tempfile
import unittest
from engine.storage.disk_index import DiskIndexStore


class TestDiskIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = DiskIndexStore(base_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_index_and_bm25_search(self):
        doc1 = self.store.add_document(
            url="https://antigravity.google.com",
            title="Antigravity Advanced Coding Assistant",
            content="Antigravity pairs with users for coding, AI search engines, and multi-agent development.",
            tags=["ai", "coding", "agent"],
        )

        doc2 = self.store.add_document(
            url="https://google.com/search",
            title="Google Search Engine",
            content="Google search organizes the world's information and makes it universally accessible.",
            tags=["search", "web", "google"],
        )

        # Query "Antigravity coding"
        results = self.store.search_bm25("Antigravity coding")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["doc_id"], doc1)
        self.assertIn("<b>Antigravity</b>", results[0]["snippet"])

        # Reload store from disk
        reloaded = DiskIndexStore(base_dir=self.temp_dir.name)
        self.assertEqual(len(reloaded.catalog), 2)
        doc = reloaded.get_document(doc1)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["title"], "Antigravity Advanced Coding Assistant")


if __name__ == "__main__":
    unittest.main()
