# Distilled Memory: Search3000

## Anchor Goal
Build an independent, Google-rivaling AI search engine ("Search3000") with Spark-X 2.6 1.7B running locally on GPU for query reformulation ("what you meant to say"), a persistent Base128 disk store (`data/indexed_sites_base128/`), and a 100% autonomous web spider that crawls strictly via hyperlink graph traversal without relying on ANY external search engine or search API.
Github: https://github.com/VicRoger27/Search3000-SE/

## Operational Contracts & Architecture Decisions
- **Zero Third-Party Search Engines/APIs**: The spider operates purely by following `<a href="...">` hyperlinks from raw starting seed URLs across the web graph.
- **Model Engine**: Spark-X 2.6 1.7B Q8_0 GGUF running via `llama-server.exe` on NVIDIA RTX 5060 Ti GPU (`-ngl 99`).
- **Disk Storage**: 7-bit Base128 files in `data/indexed_sites_base128/` (`catalog.b128`, `postings.b128`, and document files `<doc_id>.b128`).
- **Spider & Rate Limiting**:
  - Per-domain politeness and dynamic delay calculation.
  - HTTP 429/503 exponential backoff and Retry-After header parsing.
  - Robots.txt compliance via `RobotFileParser`.
  - Max redirect limit (`max_redirects=10`) preventing redirect loops.
  - Explicit HTTP 404/410 broken link logging.
  - Resetting domain backoffs on background crawler restarts.
- **Security Hardening (Phase 3)**:
  - Strict input validation on search queries (preventing memory amplification / control characters).
  - Hex-safe `doc_id` sanitization in Base128 storage preventing path traversal.
  - Configurable CORS origin headers via environment variable.

## Current Checklist
- [x] Base128 storage codec & BM25 disk indexer
- [x] Spark-X 2.6 GPU engine with sub-100ms few-shot reformulation
- [x] Eliminate third-party search engine / OpenSearch APIs
- [x] Pure hyperlink crawler with outlink graph traversal
- [x] Per-domain rate limiting, exponential backoff, robots.txt
- [x] Fix 404/410 logging, max_redirects=10, 10s robots timeout
- [x] Expand high-connectivity tech and science seed graph
- [x] Phase 3 Security Hardening (path traversal prevention, input validation)
- [x] Git sync & changelog update
