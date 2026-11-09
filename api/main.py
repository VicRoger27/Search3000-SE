"""FastAPI Backend for Search3000.

Provides Google-rivaling search APIs, SLM query intent reformulation (MiniCPM 5:2B on GPU),
high-speed autonomous hyperlink web crawler, Base128 disk storage, streaming AI Overviews,
and standalone in-engine page reader views.
"""

import asyncio
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.crawler.pure_spider import PureWebSpider
from engine.models.minicpm_engine import MiniCPMEngine
from engine.storage.disk_index import DiskIndexStore

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data" / "indexed_sites_base128"

# Global engines
store = DiskIndexStore(base_dir=str(DATA_DIR))
spider = PureWebSpider(store=store, concurrency=6)
minicpm = MiniCPMEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle."""
    try:
        await minicpm.start_server(wait_timeout=5)
    except Exception as e:
        print(f"[API] MiniCPM startup notice: {e}")

    # Launch autonomous hyperlink spider in the background
    spider.start_background()
    print("[API] Search3000 API and background spider started successfully.")

    yield

    print("[API] Shutting down Search3000...")
    spider.stop_background()
    minicpm.stop_server()
    print("[API] Clean shutdown complete.")


ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ALLOWED_FILTERS = {"all", "live_crawled", "ai"}

app = FastAPI(title="Search3000 Search Engine API", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/search")
async def search(
    q: str = Query(..., max_length=300, description="Raw user query string"),
    skip_ai: bool = Query(False, description="Whether to bypass query reformulation"),
    filter_type: str = Query("all", description="Result filter: all | live_crawled | ai"),
):
    """Executes search with MiniCPM 5:2B query reformulation and Base128 disk retrieval."""
    start_time = time.time()
    clean_q = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", q).strip()[:300]
    if filter_type not in ALLOWED_FILTERS:
        filter_type = "all"

    if not clean_q:
        return {"query": "", "results": [], "total_results": 0, "stats": store.get_stats()}

    # 1. MiniCPM 5:2B Query Intent Reformulation ("what you meant to say")
    if not skip_ai:
        reformulation = await minicpm.regenerate_query(clean_q)
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
        await spider.crawl_step(count=4)
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
    """Streams token-by-token AI Overview synthesized by MiniCPM 5:2B using Base128 results."""
    clean_q = q.strip()
    results = store.search_bm25(clean_q, top_k=5)

    async def event_generator():
        async for token in minicpm.stream_ai_overview(clean_q, results):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/page/view/{doc_id}")
def get_page_data(doc_id: str):
    """Retrieves full cached document record from Base128 disk store."""
    clean_id = re.sub(r"[^a-f0-9]", "", doc_id)
    doc = store.get_document(clean_id)
    if not doc:
        return {"error": "Document not found in Base128 index", "doc_id": clean_id}
    return {"status": "ok", "doc": doc}


@app.get("/page/{doc_id}")
def render_cached_page(doc_id: str):
    """Renders a standalone Google Cache / Reader view of an indexed page directly inside Search3000."""
    clean_id = re.sub(r"[^a-f0-9]", "", doc_id)
    doc = store.get_document(clean_id)
    if not doc:
        return HTMLResponse("<h2>404 - Document not found in Search3000 Base128 cache</h2>", status_code=404)

    title = doc.get("title", "Untitled Document")
    url = doc.get("url", "#")
    content = doc.get("content", "")
    indexed_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(doc.get("indexed_at", time.time())))

    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [content]

    paras_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title} - Search3000 Reader View</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ background: #121316; color: #e1e3e6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.7; padding: 24px; margin: 0; }}
    .reader-header {{ max-width: 820px; margin: 0 auto 28px auto; padding: 20px 24px; background: #1a1c22; border-radius: 12px; border: 1px solid #2a2d36; }}
    .badge-bar {{ display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }}
    .pill {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; border: 1px solid rgba(99, 102, 241, 0.3); }}
    .reader-title {{ font-size: 26px; font-weight: 700; color: #ffffff; margin: 0 0 8px 0; }}
    .reader-source {{ font-size: 13px; color: #9aa0a6; word-break: break-all; }}
    .reader-source a {{ color: #8ab4f8; text-decoration: none; }}
    .reader-content {{ max-width: 820px; margin: 0 auto; background: #18191f; padding: 36px 40px; border-radius: 12px; border: 1px solid #252730; font-size: 16px; color: #d0d2d6; }}
    .reader-content p {{ margin-bottom: 20px; }}
    .back-btn {{ display: inline-flex; align-items: center; gap: 6px; color: #8ab4f8; text-decoration: none; margin-bottom: 16px; font-size: 14px; font-weight: 500; }}
    .back-btn:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div style="max-width: 820px; margin: 0 auto;">
    <a href="javascript:history.back()" class="back-btn">&larr; Back to Search3000</a>
  </div>
  <header class="reader-header">
    <div class="badge-bar">
      <span class="pill">⚡ Search3000 Base128 Reader</span>
      <span class="pill">Doc ID: {clean_id}</span>
      <span class="pill">Indexed: {indexed_at}</span>
    </div>
    <h1 class="reader-title">{title}</h1>
    <div class="reader-source">Source: <a href="{url}" target="_blank" rel="noopener">{url}</a></div>
  </header>
  <main class="reader-content">
    {paras_html}
  </main>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/api/spider/status")
def get_spider_status():
    """Returns real-time status of the autonomous hyperlink crawler."""
    return {
        "spider": spider.get_status(),
        "storage": store.get_stats(),
    }


@app.post("/api/spider/toggle")
async def toggle_spider():
    """Pauses or resumes the autonomous background web spider."""
    if spider.is_running:
        spider.stop_background()
    else:
        spider.start_background()
    return {"status": "ok", "is_running": spider.is_running}


@app.post("/api/spider/crawl_now")
async def crawl_now():
    """Forces an immediate spider step forward to crawl frontier links in parallel."""
    docs = await spider.crawl_step(count=6)
    return {"status": "ok", "crawled_count": len(docs), "spider": spider.get_status()}


@app.get("/api/index/stats")
def get_index_stats():
    """Returns real-time Base128 disk storage and GPU index stats."""
    return {
        "storage": store.get_stats(),
        "spider": spider.get_status(),
        "model": {
            "name": "MiniCPM 5:2B",
            "runtime": "Ollama (CUDA GPU)",
            "gpu_offload": "100%",
            "roles": [
                "Query Intent Reformulation ('Did you mean')",
                "Live Thinking-Token Filtration",
                "Streaming Google AI Overview Synthesis",
            ],
        },
    }


# Serve Web Frontend
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(WEB_DIR / "index.html"))
