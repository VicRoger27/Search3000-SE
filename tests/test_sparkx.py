import asyncio
import unittest
from engine.models.minicpm_engine import MiniCPMEngine
from engine.models.sparkx_engine import SparkXEngine


class TestMiniCPMEngine(unittest.TestCase):
    def test_engine_initialization(self):
        engine = MiniCPMEngine(port=8085)
        self.assertEqual(engine.port, 8085)
        self.assertIn("8085", engine.base_url)
        self.assertTrue(len(engine.find_executable()) > 0)

    def test_sparkx_alias_compatibility(self):
        # Verify legacy alias works
        engine = SparkXEngine()
        self.assertIsInstance(engine, MiniCPMEngine)

    def test_fallback_reformulation_when_offline(self):
        async def run_test():
            # When unreachable, engine returns fallback gracefully without crashing
            engine = MiniCPMEngine(port=9999)
            res = await engine.regenerate_query("test query")
            self.assertEqual(res["corrected_query"], "test query")
            self.assertFalse(res["did_you_mean"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
