import asyncio
import unittest
from engine.models.sparkx_engine import SparkXEngine


class TestSparkXEngine(unittest.TestCase):
    def test_engine_initialization(self):
        engine = SparkXEngine(port=8085)
        exe = engine.find_executable()
        self.assertTrue(len(exe) > 0)

    def test_fallback_reformulation_when_offline(self):
        async def run_test():
            # When offline, engine returns fallback gracefully without crashing
            engine = SparkXEngine(port=9999)  # Non-existent port
            res = await engine.regenerate_query("test query")
            self.assertEqual(res["corrected_query"], "test query")
            self.assertFalse(res["did_you_mean"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
