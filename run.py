"""Search3000 Main Application Launcher.

Starts MiniCPM 5:2B GPU inference on RTX 5060 Ti via Ollama, mounts the Base128 disk store,
launches the FastAPI web server, and opens the Google-rivaling search interface in your browser.
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn

# Project root
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from engine.storage.disk_index import DiskIndexStore


def terminate_prior_instances():
    """Follows Window & Process Lifecycle Rule to kill any lingering server processes."""
    print("[Search3000] Checking for lingering processes on port 8000 and 8085...")
    if os.name == "nt":
        for port in [8000, 8085]:
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}"'
            try:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            except Exception:
                pass


def seed_foundational_index(store: DiskIndexStore):
    """Seeds foundational web documents if the Base128 index is completely empty."""
    if len(store.catalog) > 0:
        return

    print("[Search3000] Seeding initial Base128 disk database...")
    seeds = [
        {
            "url": "https://sparkllm.ai/spark-x2.6",
            "title": "Spark-X 2.6: Ultra-Compact Reasoning & Agentic Model",
            "content": "Spark-X 2.6 is a state-of-the-art 1.7B parameter on-device language model optimized for agentic search, coding, and controllable reasoning with high efficiency.",
            "tags": ["spark-x", "slm", "ai", "search", "reasoning"],
        },
        {
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "title": "Quantum Computing - Wikipedia",
            "content": "Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics to solve problems too complex for classical computers using qubits and superconductors.",
            "tags": ["quantum", "computing", "superconductor", "physics", "science"],
        },
        {
            "url": "https://en.wikipedia.org/wiki/Google_Search",
            "title": "Google Search - Wikipedia",
            "content": "Google Search is a search engine provided by Google, processing billions of queries daily using PageRank, machine learning, and inverted index algorithms.",
            "tags": ["google", "search", "engine", "pagerank", "algorithms"],
        },
        {
            "url": "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope",
            "title": "James Webb Space Telescope (JWST) - Wikipedia",
            "content": "The James Webb Space Telescope is a space telescope designed primarily to conduct infrared astronomy, revealing distant galaxies, star formation, and exoplanet atmospheres.",
            "tags": ["james", "webb", "telescope", "space", "astronomy", "exoplanet"],
        },
    ]

    for s in seeds:
        store.add_document(
            url=s["url"],
            title=s["title"],
            content=s["content"],
            tags=s["tags"],
            source="foundation_seed",
        )
    print(f"[Search3000] Seeded {len(seeds)} foundational documents into Base128 store.")


def main():
    print("=" * 65)
    print("           ⚡ SEARCH3000: AI SEARCH ENGINE ⚡")
    print("     Rivaling Google with MiniCPM 5:2B & Base128 Disk Store")
    print("=" * 65)

    terminate_prior_instances()

    primary_data_dir = Path(r"D:\Index\Sites")
    fallback_data_dir = ROOT_DIR / "data" / "indexed_sites_base128"
    if os.path.exists("D:\\"):
        primary_data_dir.mkdir(parents=True, exist_ok=True)
        data_dir = primary_data_dir
    else:
        data_dir = fallback_data_dir

    store = DiskIndexStore(base_dir=str(data_dir))
    seed_foundational_index(store)

    stats = store.get_stats()
    print(f"[Search3000] Base128 Store: {stats['total_documents']} documents indexed on disk.")
    print(f"[Search3000] Storage Path:  {stats['base128_folder_path']}")
    print(f"[Search3000] Starting API server on http://127.0.0.1:8000 ...")

    # Open browser slightly after start
    def open_browser():
        time.sleep(2.5)
        webbrowser.open("http://127.0.0.1:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run("api.main:app", host="127.0.0.1", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\n[Search3000] Gracefully shutting down...")
    finally:
        terminate_prior_instances()


if __name__ == "__main__":
    main()
