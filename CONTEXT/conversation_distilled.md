# Distilled Memory: Search3000

## Anchor Goal
Build an independent, Google-rivaling AI search engine ("Search3000") with Spark-X 2.6 1.7B running locally on GPU for query reformulation ("what you meant to say"), a persistent Base128 disk store (`data/indexed_sites_base128/`), and a 100% autonomous web spider that crawls strictly via hyperlink graph traversal without relying on ANY external search engine or search API.
Github: https://github.com/VicRoger27/Search3000-SE/

## Operational Contracts & Architecture Decisions
- **Zero Third-Party Search Engines/APIs**: No Google, Bing, DuckDuckGo, or Wikipedia OpenSearch API. The spider operates purely by following `<a href="...">` hyperlinks from raw starting seed URLs across the web graph.
- **Model Engine**: Spark-X 2.6 1.7B Q8_0 GGUF running via `llama-server.exe` on NVIDIA RTX 5060 Ti GPU (`-ngl 99`).
- **Disk Storage**: 7-bit Base128 files in `data/indexed_sites_base128/` (`catalog.b128`, `postings.b128`, and document files `<doc_id>.b128`).
- **Autonomous Background Spider**: Continuously pops links from frontier queue, fetches pages, extracts new links, and indexes clean text into Base128 disk store.
- **UI Tabs & Modal**:
  - Functional Settings Modal (crawler controls, stats, frontier status).
  - Search Tabs: "All" (standard dual view), "✨ AI Overview" (full AI synthesis view), "🕷️ Live Crawled" (filter to autonomous spider crawled sites).
  - Clean empty state without telling the user to input URLs.

## Current Checklist
- [x] Base128 storage codec & BM25 disk indexer
- [x] Spark-X 2.6 GPU engine with sub-100ms few-shot reformulation
- [x] Eliminate third-party search engine / OpenSearch APIs
- [x] Build pure hyperlink crawler (seed frontier -> `<a href>` extraction -> Base128 commit)
- [x] Fix Settings modal (gear icon)
- [x] Fix filter tabs ("All", "AI Overview", "Live Crawled")
- [x] Fix empty state UI messaging
- [x] Push [changelog2] to GitHub
