# Changelog 2: Pure Autonomous Web Spider & UI Fixes

### Changed & Fixed
- **100% Autonomous Hyperlink Web Spider (`engine/crawler/pure_spider.py`)**:
  - Completely eliminated all third-party search engines, search APIs, and OpenSearch endpoints.
  - Implemented pure graph traversal: starts from foundational seed URLs, fetches raw HTML, parses outlinks (`<a href>`), normalizes links, and maintains an on-disk crawling frontier.
  - Automatic background crawler continuously traverses links and saves parsed web documents to the Base128 disk store.
- **Fixed Settings & Indexer Modal**:
  - Added full settings modal dialog accessible from the top gear icon and the Base128 badge.
  - Provides real-time crawler controls (pause/resume, force step forward), frontier size, visited URL counters, and Base128 disk storage metrics.
- **Fixed Search Filter Tabs**:
  - Wired "All", "✨ AI Overview", and "🕷️ Autonomous Spider Crawled" tabs in `web/app.js` with instant filtering.
- **Polished UI & Empty State**:
  - Removed prompt telling the user to input their own URLs.
  - Added clean empty-state explaining that the autonomous spider is continuously discovering and indexing links across the web graph.
  - Replaced manual indexer sidebar widget with a live autonomous spider diagnostics panel.
- **Tests**:
  - Added `tests/test_spider.py` validating HTML link extraction and filtering. All 6 tests passing.
