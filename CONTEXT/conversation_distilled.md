# Distilled Memory: Search3000

## Anchor Goal
Build an AI-augmented search engine ("Search3000") to rival Google, where typed queries are analyzed by an SLM to regenerate what the user meant to say, searching indexed sites saved to disk in Base128 format inside a folder, featuring Google-style UI and AI Overview.
Github Repository: https://github.com/VicRoger27/Search3000-SE/

## Operational Contracts & Architecture Decisions
- **Unified Model**: Spark-X 2.6 1.7B Q8_0 GGUF running via `llama-server.exe` with full GPU offload (`-ngl 99`) on NVIDIA GeForce RTX 5060 Ti (16GB VRAM).
- **Disk Storage**: Base128 7-bit binary serialization stored in `data/indexed_sites_base128/` containing `catalog.b128`, `postings.b128`, and document files `<doc_id>.b128`.
- **Search & Retrieval**: Okapi BM25 ranker + live-fetch web crawler (`ddgs` / `httpx`) that expands the Base128 store automatically on new queries.
- **Query Reformulation**: Sub-100ms few-shot completion pipeline fixing typos and ambiguous queries into clean search terms.
- **Google AI Overview**: Real-time token streaming with bracketed source citations `[1]`, `[2]`.

## Status
- Core engine, storage, crawler, API, and web interface implemented and tested.
- All 5 unit tests passing.
- Ready for launching via `python run.py`.
