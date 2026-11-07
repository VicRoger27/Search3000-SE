# Changelog 1: Search3000 Engine Architecture & Implementation

### Added
- **Base128 Disk Store Engine (`engine/storage/base128.py` & `engine/storage/disk_index.py`)**:
  - 7-bit Base128 encoder/decoder with length-header framing and optional zlib compression.
  - Persistent on-disk index catalog, document repository, and inverted term frequency postings inside `data/indexed_sites_base128/`.
  - Okapi BM25 ranked retrieval algorithm with keyword snippet highlighting.
- **Spark-X 2.6 1.7B Model Engine (`engine/models/sparkx_engine.py`)**:
  - Full GPU offload (`-ngl 99`) to NVIDIA GeForce RTX 5060 Ti via `llama-server.exe`.
  - Sub-100ms few-shot query intent reformulation ("Did you mean / What you meant to say").
  - Content semantic tagging and summarization for web indexing.
  - Server-Sent Events (SSE) streaming for Google AI Overview with source citations `[1]`, `[2]`.
- **Live-Fetch Web Crawler (`engine/crawler/live_crawler.py`)**:
  - Asynchronous web crawler and HTML text cleaner using `httpx` and `ddgs`.
  - Real-time ingestion of live web pages directly committed into Base128 disk store on search queries.
- **FastAPI Search Engine Backend (`api/main.py`)**:
  - `/api/search`: Multi-stage search combining SLM query reformulation, Base128 disk retrieval, and live crawling.
  - `/api/ai/stream`: Token streaming for AI Overview.
  - `/api/index/stats`: Live metrics on Base128 disk storage and GPU offloading.
  - `/api/index/crawl_url`: On-demand site crawler endpoint.
- **Google-Style Minimalist UI (`web/index.html`, `web/style.css`, `web/app.js`)**:
  - Modern search interface with responsive Google colorway, instant query reformulation pill, streaming AI Overview box, and Base128 disk manager sidecar.
- **Launcher & Test Suite**:
  - `run.py`: Single-command launcher with automated port cleanup and browser startup.
  - Full unit test suite in `tests/`.
