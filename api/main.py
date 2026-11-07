"""FastAPI Backend for Search3000.

Provides Google-rivaling search APIs, SLM query intent reformulation (Spark-X 2.6 on GPU),
pure autonomous hyperlink web crawler, Base128 disk storage, and streaming AI Overviews.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.crawler.pure_spider import PureWebSpider
from engine.models.sparkx_engine import SparkXEngine
from engine.storage.disk_index import DiskIndexStore

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data" / "indexed_sites_base128"

app = FastAPI(title="Search3000 Search Engine API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engines
store = DiskIndexStore(base_dir=str(DATA_DIR))
spider = PureWebSpider(store=store)
sparkx = SparkXEngine()


@app.on_event("startup")
async def startup_event():
    """Starts Spark-X GPU engine and autonomous background spider on startup."""
    try:
        await sparkx.start_server(wait_timeout=25)
    except Exception as e:
        print(f"[API] Spark-X startup notice: {e}")

    # Launch autonomous hyperlink spider in the background
    spider.start_background()


@app.on_event("shutdown")
def shutdown_event():
    """Cleans up background spider and Spark-X engine on shutdown."""
    spider.stop_background()
    sparkx.stop_server()


@app.get("/api/search")
async def search(
    q: str = Query(..., description="Raw user query string"),
    skip_ai: bool = Query(False, description="Whether to bypass query reformulation"),
    filter_type: str = Query("all", description="Result filter: all | live_crawled | ai"),
):
    """Executes search with Spark-X query reformulation and Base128 disk retrieval."""
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

    # 2. Query Base128 on-disk index
    local_results = store.search_bm25(effective_query, top_k=30)

    # 3. If results are sparse, step the autonomous spider forward to ingest linked pages
    if len(local_results) < 3 and spider.frontier:
        await spider.crawl_step(count=2)
        local_results = store.search_bm25(effective_query, top_k=30)

    # 4. Filter by tab if requested
    if filter_type == "live_crawled":
        local_results = [r for r in local_results if r.get("source") in ("autonomous_spider", "frontier_spider")]

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
        "spider": spider.get_status(),
    }


@app.get("/api/ai/stream")
async def stream_ai(q: str = Query(..., description="Query for AI Overview")):
    """Streams token-by-token AI Overview synthesized by Spark-X 2.6 using Base128 results."""
    clean_q = q.strip()
    results = store.search_bm25(clean_q, top_k=5)

    async def event_generator():
        async for token in sparkx.stream_ai_overview(clean_q, results):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/spider/status")
def get_spider_status():
    """Returns real-time status of the autonomous hyperlink crawler."""
    return {
        "spider": spider.get_status(),
        "storage": store.get_stats(),
    }


@app.post("/api/spider/toggle")
def toggle_spider():
    """Pauses or resumes the autonomous background web spider."""
    if spider.is_running:
        spider.stop_background()
    else:
        spider.start_background()
    return {"status": "ok", "is_running": spider.is_running}


@app.post("/api/spider/crawl_now")
async def crawl_now():
    """Forces an immediate spider step forward to crawl frontier links."""
    docs = await spider.crawl_step(count=2)
    return {"status": "ok", "crawled_count": len(docs), "spider": spider.get_status()}


@app.get("/api/index/stats")
def get_index_stats():
    """Returns real-time Base128 disk storage and GPU index stats."""
    return {
        "storage": store.get_stats(),
        "spider": spider.get_status(),
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
