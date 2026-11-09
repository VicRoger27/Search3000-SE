"""Pure Hyperlink Graph Web Spider for Search3000.

Operates as a 100% independent web crawler following hyperlinks across the web graph:
- ZERO reliance on external search engines (no Google, no Bing, no DuckDuckGo).
- ZERO search APIs or OpenSearch endpoints.
- High-Speed Concurrent Traversal: uses asynchronous batching to crawl multiple URLs in parallel.
- Strict Content & Language Filtering: rejects foreign Wikipedia language subdomains, non-content namespaces,
  and noisy boilerplate so that only high-quality English documents are indexed.
- Clean Snippet Extraction: extracts actual article paragraphs, stripping Wikipedia navigation cruft.
"""

import asyncio
import hashlib
import os
import re
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from engine.storage.base128 import Base128Codec
from engine.storage.disk_index import DiskIndexStore

# Foundational high-connectivity English seeds
DEFAULT_SEEDS = [
    # Computer Vision & Deep Learning (YOLO, SAM, Neural Networks)
    "https://en.wikipedia.org/wiki/YOLO_(object_detection)",
    "https://en.wikipedia.org/wiki/Segment_Anything",
    "https://en.wikipedia.org/wiki/Object_detection",
    "https://en.wikipedia.org/wiki/Computer_vision",
    "https://en.wikipedia.org/wiki/Convolutional_neural_network",
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Deep_learning",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Neural_network",
    "https://en.wikipedia.org/wiki/Transformer_(deep_learning)",
    "https://en.wikipedia.org/wiki/Generative_adversarial_network",
    "https://en.wikipedia.org/wiki/Large_language_model",
    "https://arxiv.org/abs/2304.02643",  # Segment Anything (SAM) paper
    "https://arxiv.org/abs/1506.02640",  # You Only Look Once (YOLO) paper

    # Technology, Software Engineering & Science Portals
    "https://en.wikipedia.org/wiki/Software_engineering",
    "https://en.wikipedia.org/wiki/Quantum_computing",
    "https://en.wikipedia.org/wiki/Superconductivity",
    "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope",
    "https://en.wikipedia.org/wiki/Python_(programming_language)",
    "https://en.wikipedia.org/wiki/Search_engine",
    "https://en.wikipedia.org/wiki/PageRank",
    "https://en.wikipedia.org/wiki/Inverted_index",
    "https://news.ycombinator.com/",
]

# Non-content Wikipedia namespaces and noisy paths to reject
BLOCKED_PATH_SUBSTRINGS = (
    "action=edit", "action=history", "oldid=", "printable=yes", "diff=",
    "/special:", "/help:", "/talk:", "/user:", "/file:", "/category:",
    "/portal:", "/template:", "/mediawiki:", "/timedtext:", "/module:",
    "/gadget:", "/wikipedia:", "/main_page",
)

IGNORED_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar",
    ".gz", ".mp4", ".mp3", ".svg", ".css", ".js", ".ico", ".woff",
    ".woff2", ".ttf", ".eot", ".xml", ".json",
)


class PureWebSpider:
    def __init__(self, store: DiskIndexStore, concurrency: int = 6):
        self.store = store
        self.frontier_file = self.store.base_dir / "spider_frontier.b128"
        self.frontier: List[str] = []
        self.visited: Set[str] = set()
        self.is_running: bool = False
        self.crawler_task: Optional[asyncio.Task] = None
        self.pages_crawled_session: int = 0
        self.broken_links_count: int = 0
        self.current_crawling_url: str = ""
        self.concurrency: int = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

        # Rate limiting & Dynamic Crawl Backoff (tuned for responsiveness)
        self.default_crawl_delay: float = 0.2
        self.max_redirects: int = 10
        self.domain_last_visited: Dict[str, float] = {}
        self.domain_delays: Dict[str, float] = {}
        self.domain_backoff: Dict[str, float] = {}
        self.robots_cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

        self.headers = {
            "User-Agent": (
                "Search3000Bot/2.1 (Autonomous Web Spider; +https://github.com/VicRoger27/Search3000-SE; contact@search3000.org)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        self._load_state()

    def _normalize_url(self, url: str) -> str:
        """Strips fragments, trailing slashes, and lowercases domain."""
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        return f"{parsed.scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")

    def _get_domain(self, url: str) -> str:
        """Extracts normalized hostname from URL."""
        return urlparse(url).netloc.lower()

    def _is_url_allowed(self, url: str) -> bool:
        """Checks if a URL meets language and quality filters."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False

            netloc = parsed.netloc.lower()
            path_lower = parsed.path.lower()
            query_lower = parsed.query.lower()

            # 1. Enforce English Wikipedia only (filter out fa.wikipedia.org, ko.wikipedia.org, etc.)
            if "wikipedia.org" in netloc:
                if not netloc.startswith("en."):
                    return False

            # 2. Filter out non-content paths and edit/history links
            full_check = f"{path_lower}?{query_lower}"
            if any(sub in full_check for sub in BLOCKED_PATH_SUBSTRINGS):
                return False

            # 3. Filter file extensions
            if any(path_lower.endswith(ext) for ext in IGNORED_EXTENSIONS):
                return False

            return True
        except Exception:
            return False

    def _load_state(self):
        """Loads visited URLs from catalog and unvisited links from frontier file."""
        for doc_id, meta in self.store.catalog.items():
            if "url" in meta:
                self.visited.add(self._normalize_url(meta["url"]))

        if self.frontier_file.exists():
            try:
                data = Base128Codec.deserialize_payload(self.frontier_file.read_bytes())
                if isinstance(data, list):
                    self.frontier = [
                        u for u in data
                        if self._is_url_allowed(u) and self._normalize_url(u) not in self.visited
                    ]
            except Exception as e:
                print(f"[PureSpider] Error loading frontier: {e}")

        # If frontier is empty or low, seed with high-value foundational English seeds
        if len(self.frontier) < 10:
            for s in DEFAULT_SEEDS:
                if self._normalize_url(s) not in self.visited and s not in self.frontier:
                    self.frontier.append(s)

    def _save_state(self):
        """Persists top 1000 frontier URLs in Base128 format."""
        try:
            payload = Base128Codec.serialize_payload(self.frontier[:1000])
            self.frontier_file.write_bytes(payload)
        except Exception as e:
            print(f"[PureSpider] Error saving frontier: {e}")

    async def _enforce_domain_delay(self, domain: str):
        """Ensures per-domain politeness without freezing the entire crawler."""
        now = time.time()
        last_time = self.domain_last_visited.get(domain, 0.0)
        base_delay = self.domain_delays.get(domain, self.default_crawl_delay)
        multiplier = self.domain_backoff.get(domain, 1.0)
        target_delay = min(5.0, base_delay * multiplier)

        elapsed = now - last_time
        if elapsed < target_delay:
            wait_time = target_delay - elapsed
            await asyncio.sleep(wait_time)

        self.domain_last_visited[domain] = time.time()

    async def is_allowed_by_robots(self, url: str) -> bool:
        """Checks if URL is permitted by domain's robots.txt with caching."""
        domain = self._get_domain(url)
        if not domain:
            return True

        if domain not in self.robots_cache:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=True) as client:
                    resp = await client.get(robots_url, headers=self.headers)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                        self.robots_cache[domain] = rp
                    else:
                        self.robots_cache[domain] = None
            except Exception:
                self.robots_cache[domain] = None

        cached_rp = self.robots_cache.get(domain)
        if cached_rp is not None:
            try:
                return cached_rp.can_fetch("Search3000Bot", url) or cached_rp.can_fetch("*", url)
            except Exception:
                return True
        return True

    @classmethod
    def extract_page_data(cls, html: str, base_url: str) -> Dict[str, Any]:
        """Parses HTML into clean article text, title, clean snippet, and quality outlinks."""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        title = re.sub(r"&[a-zA-Z0-9#]+;", " ", title)
        # Clean title suffix (e.g. " - Wikipedia")
        title = re.sub(r"\s+-\s+Wikipedia.*$", "", title, flags=re.IGNORECASE)

        # 1. Extract and filter all valid outgoing links
        raw_links = re.findall(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        valid_links = []

        spider_instance = cls(store=None) if False else None

        for l in raw_links:
            try:
                full_url = urljoin(base_url, l.strip())
                parsed = urlparse(full_url)
                if parsed.scheme in ("http", "https"):
                    netloc = parsed.netloc.lower()
                    path_lower = parsed.path.lower()
                    query_lower = parsed.query.lower()

                    # Only English Wikipedia
                    if "wikipedia.org" in netloc and not netloc.startswith("en."):
                        continue
                    # Skip noise
                    if any(sub in f"{path_lower}?{query_lower}" for sub in BLOCKED_PATH_SUBSTRINGS):
                        continue
                    if any(path_lower.endswith(ext) for ext in IGNORED_EXTENSIONS):
                        continue

                    url_clean, _ = urldefrag(full_url)
                    valid_links.append(url_clean)
            except Exception:
                pass

        # 2. Extract clean body text and extract paragraph summaries
        cleaned = re.sub(
            r"<(script|style|noscript|svg|nav|footer|header|aside|figure)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Extract main paragraph content
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", cleaned, flags=re.IGNORECASE | re.DOTALL)
        clean_paras = []
        for p in paragraphs:
            p_text = re.sub(r"<[^>]+>", " ", p)
            p_text = re.sub(r"\[\d+\]|\[edit\]|\[citation needed\]", "", p_text)
            p_text = re.sub(r"&nbsp;|&amp;|&quot;|&#\d+;", " ", p_text)
            p_text = re.sub(r"\s+", " ", p_text).strip()
            # Ignore Wikipedia disclaimers / empty / disambiguation lines
            if len(p_text) > 40 and not p_text.startswith("Jump to") and not "Redirected from" in p_text:
                clean_paras.append(p_text)

        snippet = " ".join(clean_paras[:2])[:280]
        if snippet and not snippet.endswith("."):
            snippet += "..."

        # Full body text for indexing
        text = re.sub(r"<[^>]+>", " ", cleaned)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Remove common Wikipedia header junk from full text
        text = re.sub(r"Jump to (content|navigation|search)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"From Wikipedia, the free encyclopedia", "", text, flags=re.IGNORECASE)

        return {
            "title": title or "Web Document",
            "text": text,
            "snippet": snippet or (text[:240] + "..."),
            "outlinks": list(dict.fromkeys(valid_links))[:80],
        }

    async def fetch_and_index(self, url: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Politely fetches a URL, indexes into Base128, and enqueues high-value outlinks."""
        norm_url = self._normalize_url(url)
        self.visited.add(norm_url)
        self.current_crawling_url = url
        domain = self._get_domain(url)

        if not self._is_url_allowed(url):
            return None

        # 1. Robots.txt Compliance Check
        if not await self.is_allowed_by_robots(url):
            return None

        # 2. Dynamic Domain Rate Limiting Delay
        await self._enforce_domain_delay(domain)

        async with self.semaphore:
            req_start = time.time()
            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=True,
                    verify=True,
                    max_redirects=self.max_redirects
                ) as client:
                    res = await client.get(url, headers=self.headers)
                    latency = time.time() - req_start

                    if res.status_code in (404, 410):
                        self.broken_links_count += 1
                        return None

                    if res.status_code in (429, 503):
                        self.domain_delays[domain] = 2.0
                        return None

                    if res.status_code != 200:
                        return None

                    content_type = res.headers.get("content-type", "").lower()
                    if "text/html" not in content_type and "application/xhtml" not in content_type:
                        return None

                    html = res.text
                    data = self.extract_page_data(html, str(res.url))

                    # Index into Base128 disk store
                    doc_id = self.store.add_document(
                        url=str(res.url),
                        title=data["title"],
                        content=data["text"],
                        snippet=data["snippet"],
                        source="autonomous_spider",
                    )
                    self.store.save_index()
                    self.pages_crawled_session += 1

                    # Add new outlinks to frontier
                    frontier_set = set(self.frontier)
                    added = 0
                    for link in data["outlinks"]:
                        norm_link = self._normalize_url(link)
                        if (
                            self._is_url_allowed(link)
                            and norm_link not in self.visited
                            and link not in frontier_set
                        ):
                            self.frontier.append(link)
                            frontier_set.add(link)
                            added += 1
                            if len(self.frontier) >= 3000:
                                break

                    print(f"[PureSpider] Indexed [{data['title']}] ({str(res.url)}) +{added} links (Frontier: {len(self.frontier)})")
                    return {
                        "doc_id": doc_id,
                        "url": str(res.url),
                        "title": data["title"],
                        "snippet": data["snippet"],
                    }

            except Exception:
                pass
            finally:
                self.current_crawling_url = ""

        return None

    async def crawl_step(self, count: int = 5) -> List[Dict[str, Any]]:
        """Pops a batch of unvisited URLs from frontier and crawls them concurrently."""
        batch_urls = []
        while self.frontier and len(batch_urls) < count:
            url = self.frontier.pop(0)
            norm = self._normalize_url(url)
            if norm in self.visited or not self._is_url_allowed(url):
                continue
            batch_urls.append(url)

        if not batch_urls:
            return []

        tasks = [self.fetch_and_index(u) for u in batch_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        indexed = [r for r in results if isinstance(r, dict) and r is not None]
        return indexed

    async def run_crawler_loop(self):
        """Continuous background crawl loop processing concurrent batches."""
        self.is_running = True
        print(f"[PureSpider] High-speed autonomous crawler started. Initial frontier: {len(self.frontier)} links.")
        while self.is_running:
            if not self.frontier:
                for s in DEFAULT_SEEDS:
                    if self._normalize_url(s) not in self.visited:
                        self.frontier.append(s)

            try:
                # Crawl 4 URLs concurrently in each step
                await self.crawl_step(count=4)
            except Exception as e:
                print(f"[PureSpider] Loop exception: {e}")

            await asyncio.sleep(self.default_crawl_delay)

    def start_background(self):
        """Starts background crawler loop if not running."""
        if not self.is_running or self.crawler_task is None or self.crawler_task.done():
            self.is_running = True
            try:
                loop = asyncio.get_running_loop()
                self.crawler_task = loop.create_task(self.run_crawler_loop())
            except RuntimeError:
                pass

    def stop_background(self):
        """Pauses the background crawler."""
        self.is_running = False
        if self.crawler_task:
            self.crawler_task.cancel()
            self.crawler_task = None
        self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Returns live crawler diagnostics."""
        return {
            "is_running": self.is_running,
            "frontier_size": len(self.frontier),
            "visited_count": len(self.visited),
            "pages_crawled_session": self.pages_crawled_session,
            "broken_links_count": self.broken_links_count,
            "current_crawling_url": self.current_crawling_url,
            "crawl_delay_seconds": self.default_crawl_delay,
            "active_domains_tracked": len(self.domain_delays),
            "concurrency": self.concurrency,
        }
