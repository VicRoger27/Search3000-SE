# Changelog 4: Rate Limiting, Dynamic Crawl Backoff & Robots Compliance

### Added & Improved
- **Per-Domain Politeness & Dynamic Throttling (`engine/crawler/pure_spider.py`)**:
  - Implemented per-domain last-crawl timestamp tracking (`domain_last_visited`) and independent domain delay calculation.
  - Ensures different domains can be crawled efficiently without serial blocking, while strictly preventing request hammering on any single host.
- **HTTP 429 / 503 Exponential Backoff & Retry-After**:
  - Automatically parses `Retry-After` HTTP headers on rate-limited responses.
  - Applies exponential backoff multipliers (up to 16x) and re-enqueues dropped links so they are safely revisited later.
- **Robots.txt Exclusion Compliance**:
  - Integrated `urllib.robotparser.RobotFileParser` with in-memory domain caching.
  - Automatically checks `can_fetch("Search3000Bot", url)` before every crawl request, skipping disallowed paths politely.
- **Adaptive Response-Time Backoff**:
  - Measures HTTP latency per domain; if a server shows signs of strain (>2.5s response time), the domain delay automatically scales up by +0.5s to relieve pressure.
