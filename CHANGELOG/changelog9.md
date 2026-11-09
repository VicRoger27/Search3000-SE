# Changelog 9: MiniCPM 5:2B Integration, High-Speed Concurrent Spider & In-Engine Reader

### Added & Refined
- **MiniCPM 5:2B Engine via Ollama (`engine/models/minicpm_engine.py`)**:
  - Replaced Spark-X with `maternion/minicpm5:2b` executing directly on NVIDIA RTX 5060 Ti GPU through local Ollama.
  - Implemented live thinking token filtration (`<think>...</think>`), preventing reasoning leakage into streaming AI Overviews and query intent reformulation.
  - Established backwards-compatible `SparkXEngine = MiniCPMEngine` alias in `engine/models/sparkx_engine.py`.
- **High-Speed Concurrent Autonomous Spider (`engine/crawler/pure_spider.py`)**:
  - Replaced single-URL sequential crawling with concurrent batch crawling (`asyncio.gather` with concurrency semaphore = 6).
  - Enforced strict English-only domain gates (`en.wikipedia.org`), rejecting foreign language subdomains (e.g. `fa.wikipedia.org`, `ko.wikipedia.org`) and non-content namespaces (`Special:`, `Help:`, `User:`, `action=edit`, `action=history`).
  - Implemented clean article paragraph extraction and snippet generation, stripping Wikipedia navigation cruft.
  - Pruned 50 non-English/boilerplate documents from existing Base128 index, leaving 71 high-quality English documents.
- **In-Engine Cached Page Reader & Zero Google Favicon Hand-Off (`api/main.py`, `web/`)**:
  - Added `/page/{doc_id}` delivering standalone, distraction-free Google Reader / Archive views of indexed sites directly from Search3000's Base128 disk store.
  - Added `/api/page/view/{doc_id}` API endpoint for programmatic document retrieval.
  - Eliminated external `google.com/s2/favicons` dependencies; introduced local deterministic pastel SVG domain badges.
  - Added dual action buttons on all result cards: `⚡ Read In-Engine` and `🌐 Original Link`.
- **Expanded Test Suite (`tests/`)**:
  - Updated API and engine tests; verified all 23 unit tests passing in 9.0s.
  - Code audit score: 100.0% (16/16 checks passed).
