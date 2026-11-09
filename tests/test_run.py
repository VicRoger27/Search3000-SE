"""Tests for Search3000 Main Launcher (run.py)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from engine.storage.disk_index import DiskIndexStore
import run


class TestRunLauncher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="search3000_run_test_")
        self.store = DiskIndexStore(base_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_terminate_prior_instances(self):
        """Test terminate_prior_instances executes without throwing errors."""
        try:
            run.terminate_prior_instances()
        except Exception as e:
            self.fail(f"terminate_prior_instances raised unexpected exception: {e}")

    def test_seed_foundational_index(self):
        """Test seed_foundational_index seeds initial documents on fresh store."""
        self.assertEqual(len(self.store.catalog), 0)
        run.seed_foundational_index(self.store)
        self.assertGreater(len(self.store.catalog), 0)

        results = self.store.search_bm25("quantum", top_k=5)
        self.assertGreater(len(results), 0)
        self.assertIn("quantum", results[0]["title"].lower())

    def test_seed_foundational_index_idempotency(self):
        """Test seed_foundational_index is a no-op if store already contains documents."""
        run.seed_foundational_index(self.store)
        count_after_first_seed = len(self.store.catalog)

        # Call again — should be a no-op
        run.seed_foundational_index(self.store)
        self.assertEqual(len(self.store.catalog), count_after_first_seed)

    def test_launcher_attributes(self):
        """Test run.py exports expected constants and entry points."""
        self.assertTrue(hasattr(run, "ROOT_DIR"))
        self.assertTrue(isinstance(run.ROOT_DIR, Path))
        self.assertTrue(callable(run.main))


if __name__ == "__main__":
    unittest.main()
