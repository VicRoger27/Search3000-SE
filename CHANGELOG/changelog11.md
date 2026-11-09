# Changelog 11: D:\Index\Sites Target, Pure llama.cpp Engine (Zero Ollama), & Sub-50ms Non-Blocking Search

### Added & Refined
- **Target Storage Relocated to `D:\Index\Sites` (`api/main.py`, `run.py`)**:
  - Configured `D:\Index\Sites` as the primary storage destination for Base128 document bodies, catalogs, postings, and frontier queues.
  - Copied all 105 indexed web documents and 22,956 vocabulary postings to `D:\Index\Sites`.
- **Zero Ollama Architecture (`engine/models/minicpm_engine.py`)**:
  - Completely detached from Ollama.
  - Re-anchored to direct GPU execution via `llama-server.exe` on port 8085 with `MiniCPM5-2B-Q4_K_M.gguf` using 100% layer offloading (`-ngl 99`).
  - Switched query intent reformulation to few-shot `/v1/completions` with `stop: ["\n"]`, dropping reformulation latency from 13.38s down to **120ms**.
  - Configured real-time streaming AI Overviews directly through `/v1/completions` for instant token-by-token synthesis.
- **Lightning Non-Blocking Search Pipeline (`api/main.py`)**:
  - Eliminated synchronous crawling within the user's `/api/search` request path.
  - Offloaded sparse-frontier crawls to background tasks (`asyncio.create_task`), dropping search response times from 13.38 seconds down to **< 50 milliseconds**.
- **Increased Crawler Indexing Concurrency**:
  - Boosted crawler concurrency semaphore to 8 concurrent parallel workers for high-speed indexing into `D:\Index\Sites`.
