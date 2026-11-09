import asyncio
import unittest
from engine.models.minicpm_engine import MiniCPMEngine
from engine.models.sparkx_engine import SparkXEngine


class TestMiniCPMEngine(unittest.TestCase):
    def test_engine_initialization(self):
        engine = MiniCPMEngine()
        self.assertEqual(engine.model_name, "maternion/minicpm5:2b")
        self.assertIn("11434", engine.base_url)

    def test_sparkx_alias_compatibility(self):
        # Verify legacy alias works
        engine = SparkXEngine()
        self.assertIsInstance(engine, MiniCPMEngine)

    def test_fallback_reformulation_when_offline(self):
        async def run_test():
            # When unreachable, engine returns fallback gracefully without crashing
            engine = MiniCPMEngine(base_url="http://127.0.0.1:9999", timeout=1.0)
            res = await engine.regenerate_query("test query")
            self.assertEqual(res["corrected_query"], "test query")
            self.assertFalse(res["did_you_mean"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
