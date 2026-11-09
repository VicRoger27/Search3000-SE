# Distilled Memory: Search3000

## Anchor Goal
Build an independent, Google-rivaling AI search engine ("Search3000") with Spark-X 2.6 1.7B running locally on GPU for query reformulation ("what you meant to say"), a persistent Base128 disk store (`data/indexed_sites_base128/`), and a 100% autonomous web spider that crawls strictly via hyperlink graph traversal without relying on ANY external search engine or search API.
Github: https://github.com/VicRoger27/Search3000-SE/

## Active Agents & Roles
- **Antigravity (Lead Coding AI - Gemini 3.8 Flash Med)**: Multi-file architecture, feature execution, git commits, changelogs.
- **Cache Cappy (Quality & Security Watchdog - Qwen 3.5 9B)**: Multi-pass code inspection, roadmap planning, security audits.
- **Teo (Autonomous Scout & Test Runner - MiniCPM:2B)**: Fast terminal runner. Note: Working directory is `C:\Users\Victor\Antigravity Projects\General\Search3000`.

## Operational Contracts & Architecture Decisions
- **Zero Third-Party Search Engines/APIs**: Pure hyperlink graph crawler (`pure_spider.py`) starting from foundational seeds.
- **Model Engine**: Spark-X 2.6 1.7B Q8_0 GGUF running on NVIDIA RTX 5060 Ti GPU (`-ngl 99`).
- **Disk Storage**: 7-bit Base128 files in `data/indexed_sites_base128/`.
- **Crawler Resilience**: Per-domain rate limiting, exponential backoff, robots.txt compliance, max redirect protection (`max_redirects=10`), HTTP 404/410 tracking.
- **Security Hardening**: Sanitized hexadecimal `doc_id` path-traversal safety, 300-char query limit, configurable CORS.
- **Baseline Status**: Baseline verified 100% passing by Cache Cappy (all tests green).

## Current Checklist
- [x] Base128 storage codec & BM25 disk indexer
- [x] Spark-X 2.6 GPU engine with sub-100ms few-shot reformulation
- [x] 100% pure hyperlink spider with outlink graph traversal
- [x] Rate limiting, exponential backoff, robots.txt compliance
- [x] Baseline test verification confirmed passing by Cache Cappy
- [ ] Active: Cache Cappy & Teo Security & Quality Gates audit (api/main.py, engine/crawler/)
- [ ] Upcoming: User live test-drive and UI verification
- [ ] Antigravity patch execution on Capy audit findings
