"""FastAPI Backend for Search3000.

Provides Google-rivaling search APIs, SLM query intent reformulation,
live web crawler ingestion, Base128 disk statistics, and streaming AI Overviews.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.crawler.live_crawler import LiveCrawler
from engine.models.sparkx_engine import SparkXEngine
from engine.storage.disk_index import DiskIndexStore

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data" / "indexed_sites_base128"

app = FastAPI(title="Search3000 Search Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engines
store = DiskIndexStore(base_dir=str(DATA_DIR))
crawler = LiveCrawler(store=store)
sparkx = SparkXEngine()


def seed_foundation():
    if len(store.catalog) == 0:
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

seed_foundation()


class CrawlRequest(BaseModel):
    url: str


@app.on_event("startup")
async def startup_event():
    """Starts the Spark-X GPU engine in the background on startup."""
    try:
        await sparkx.start_server(wait_timeout=25)
    except Exception as e:
        print(f"[API] Notice on model startup: {e}")


@app.on_event("shutdown")
def shutdown_event():
    """Ensures clean shutdown of model server per user rules."""
    sparkx.stop_server()


@app.get("/api/search")
async def search(
    q: str = Query(..., description="Raw user query string"),
    skip_ai: bool = Query(False, description="Whether to bypass query reformulation"),
):
    """Executes search with Spark-X query reformulation and hybrid indexing."""
    start_time = time.time()
    clean_q = q.strip()
    if not clean_q:
        return {"query": "", "results": [], "total_results": 0, "stats": store.get_stats()}

    # 1. Spark-X Query Intent Reformulation ("what you meant to say")
    if not skip_ai:
        reformulation = await sparkx.regenerate_query(clean_q)
    else:
        reformulation = {
            "corrected_query": clean_q,
            "did_you_mean": False,
            "reason": "",
            "raw_query": clean_q,
        }

    effective_query = (
        reformulation["corrected_query"] if reformulation["did_you_mean"] else clean_q
    )

    # 2. Query local Base128 index
    local_results = store.search_bm25(effective_query, top_k=20)

    # 3. If local index has few results, live fetch & index new web pages
    if len(local_results) < 5:
        await crawler.fetch_and_index_query(effective_query, max_fetch=6)
        # Re-query after ingestion
        local_results = store.search_bm25(effective_query, top_k=25)

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "raw_query": clean_q,
        "effective_query": effective_query,
        "did_you_mean": reformulation["did_you_mean"],
        "corrected_query": reformulation["corrected_query"],
        "reason": reformulation.get("reason", ""),
        "total_results": len(local_results),
        "results": local_results,
        "time_ms": elapsed_ms,
        "stats": store.get_stats(),
    }


@app.get("/api/ai/stream")
async def stream_ai(q: str = Query(..., description="Query for AI Overview")):
    """Streams token-by-token AI Overview synthesized by Spark-X 2.6 with source citations."""
    clean_q = q.strip()
    results = store.search_bm25(clean_q, top_k=5)
    if not results:
        # Crawl quickly if empty
        await crawler.fetch_and_index_query(clean_q, max_fetch=4)
        results = store.search_bm25(clean_q, top_k=5)

    async def event_generator():
        async for token in sparkx.stream_ai_overview(clean_q, results):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/index/crawl_url")
async def crawl_custom_url(req: CrawlRequest):
    """Explicitly crawls and commits a URL to the Base128 disk store."""
    doc = await crawler.index_custom_url(req.url)
    if not doc:
        return {"status": "error", "message": f"Could not crawl {req.url}"}
    return {"status": "success", "document": doc, "stats": store.get_stats()}


@app.get("/api/index/stats")
def get_index_stats():
    """Returns real-time Base128 disk storage and GPU index stats."""
    return {
        "storage": store.get_stats(),
        "model": {
            "name": "Spark-X 2.6 1.7B Q8_0",
            "runtime": "llama-server (CUDA GPU)",
            "gpu_offload": "100% (n_gpu_layers=99)",
            "roles": [
                "Query Intent Reformulation ('Did you mean')",
                "Indexing Semantic Understanding & Tagging",
                "Conversational AI Overview Synthesis",
            ],
        },
    }


# Serve Web Frontend
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(WEB_DIR / "index.html"))
