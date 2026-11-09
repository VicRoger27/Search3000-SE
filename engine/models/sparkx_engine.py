"""Spark-X / MiniCPM Model Engine Compatibility Layer for Search3000.

Aliases MiniCPMEngine to power query reformulation and streaming AI Overviews
using the high-performance MiniCPM 5:2B model running on GPU via Ollama.
"""

from engine.models.minicpm_engine import MiniCPMEngine

# Backwards-compatible alias so legacy imports continue to work seamlessly
SparkXEngine = MiniCPMEngine

__all__ = ["SparkXEngine", "MiniCPMEngine"]
