# Changelog 5: Crawl Resilience & Security Hardening (Audit v2.0.3)

### Changed & Hardened
- **Crawler Resilience Edge Cases (`engine/crawler/pure_spider.py`)**:
  - **Redirect Loop Protection**: Configured `max_redirects = 10` in `httpx.AsyncClient` with `TooManyRedirects` exception handling to prevent infinite redirect loops.
  - **Broken Link Detection**: Added explicit HTTP 404 & 410 detection and tracking (`broken_links_count`), logging broken links rather than silently skipping.
  - **Robots.txt Timeout**: Increased robots.txt HTTP client timeout to `10.0` seconds to support slower networks and large robots policies.
  - **Spider Restart Delay Reset**: `start_background()` now clears stale `domain_delays`, `domain_backoff`, and `domain_last_visited` timestamps on restart.
  - **High-Connectivity Seed Graph**: Added high-connectivity hubs to `DEFAULT_SEEDS` (Software Engineering, Neural Networks, Transformers, GANs, Portal:Technology, Portal:Science).
- **Security Hardening (`engine/storage/disk_index.py` & `api/main.py`)**:
  - **Path Traversal Protection**: Sanitized `doc_id` in `DiskIndexStore.get_document()` with strict hexadecimal filtering (`re.sub(r'[^a-f0-9]', '', doc_id)`) completely neutralizing directory traversal attacks (`../`).
  - **API Input Sanitization**: Added character stripping (`[\x00-\x1f\x7f-\x9f]`) and bounded query length (`max_length=300`) to prevent memory/buffer amplification attacks.
  - **Filter Whitelisting**: Restricted `filter_type` to verified whitelist `{"all", "live_crawled", "ai"}`.
  - **Configurable CORS**: Replaced wildcard CORS with environment variable-driven origins via `CORS_ORIGINS`.
