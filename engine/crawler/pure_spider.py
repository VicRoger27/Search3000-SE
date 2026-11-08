"""Pure Hyperlink Graph Web Spider for Search3000.

Operates as a 100% independent web crawler following hyperlinks across the web graph:
- ZERO reliance on external search engines (no Google, no Bing, no DuckDuckGo).
- ZERO search APIs or OpenSearch endpoints.
- Pure hyperlink traversal: fetches seed pages, extracts <a href="..."> outlinks,
  normalizes them into an on-disk frontier, and commits parsed documents to Base128.
- Rate Limiting & Dynamic Crawl Backoff: per-domain politeness, robots.txt compliance,
  HTTP 429/503 exponential backoff, and adaptive latency-based throttling.
"""

import asyncio
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

# Foundational seeds across computer vision, AI, science, technology, and portals
DEFAULT_SEEDS = [
    # Computer Vision & Models (YOLO, SAM, Deep Learning)
    "https://en.wikipedia.org/wiki/YOLO_(object_detection)",
    "https://en.wikipedia.org/wiki/Segment_Anything",
    "https://en.wikipedia.org/wiki/Object_detection",
    "https://en.wikipedia.org/wiki/Computer_vision",
    "https://en.wikipedia.org/wiki/Convolutional_neural_network",
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Deep_learning",
    "https://en.wikipedia.org/wiki/Large_language_model",
    "https://arxiv.org/abs/2304.02643",  # Segment Anything (SAM) paper
    "https://arxiv.org/abs/1506.02640",  # You Only Look Once (YOLO) paper

    # Technology, Science & Web Portals
    "https://en.wikipedia.org/wiki/Quantum_computing",
    "https://en.wikipedia.org/wiki/Superconductivity",
    "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope",
    "https://en.wikipedia.org/wiki/Python_(programming_language)",
    "https://news.ycombinator.com/",
    "https://en.wikipedia.org/wiki/Main_Page",
]


class PureWebSpider:
    def __init__(self, store: DiskIndexStore):
        self.store = store
        self.frontier_file = self.store.base_dir / "spider_frontier.b128"
        self.frontier: List[str] = []
        self.visited: Set[str] = set()
        self.is_running: bool = False
        self.crawler_task: Optional[asyncio.Task] = None
        self.pages_crawled_session: int = 0
        self.current_crawling_url: str = ""

        # Rate limiting & Dynamic Crawl Backoff
        self.default_crawl_delay: float = 1.0
        self.domain_last_visited: Dict[str, float] = {}
        self.domain_delays: Dict[str, float] = {}
        self.domain_backoff: Dict[str, float] = {}
        self.robots_cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

        self.headers = {
            "User-Agent": (
                "Search3000Bot/2.0 (Autonomous Web Spider; +https://github.com/VicRoger27/Search3000-SE; contact@search3000.org)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
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

    def _load_state(self):
        """Loads visited URLs from catalog and unvisited links from frontier file."""
        for doc_id, meta in self.store.catalog.items():
            if "url" in meta:
                self.visited.add(self._normalize_url(meta["url"]))

        if self.frontier_file.exists():
            try:
                data = Base128Codec.deserialize_payload(self.frontier_file.read_bytes())
                if isinstance(data, list):
                    self.frontier = [u for u in data if self._normalize_url(u) not in self.visited]
            except Exception as e:
                print(f"[PureSpider] Error loading frontier: {e}")

        # If frontier is empty, populate from default seeds
        if not self.frontier:
            for s in DEFAULT_SEEDS:
                if self._normalize_url(s) not in self.visited:
                    self.frontier.append(s)

    def _save_state(self):
        """Persists top 500 frontier URLs in Base128 format."""
        try:
            payload = Base128Codec.serialize_payload(self.frontier[:500])
            self.frontier_file.write_bytes(payload)
        except Exception as e:
            print(f"[PureSpider] Error saving frontier: {e}")

    async def _enforce_domain_delay(self, domain: str):
        """Ensures politeness: enforces per-domain rate limiting with dynamic backoff."""
        now = time.time()
        last_time = self.domain_last_visited.get(domain, 0.0)
        base_delay = self.domain_delays.get(domain, self.default_crawl_delay)
        multiplier = self.domain_backoff.get(domain, 1.0)
        target_delay = base_delay * multiplier

        elapsed = now - last_time
        if elapsed < target_delay:
            wait_time = target_delay - elapsed
            await asyncio.sleep(wait_time)

        self.domain_last_visited[domain] = time.time()

    async def is_allowed_by_robots(self, url: str) -> bool:
        """Checks if URL is permitted by the domain's robots.txt policy."""
        domain = self._get_domain(url)
        if not domain:
            return True

        if domain not in self.robots_cache:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            try:
                async with httpx.AsyncClient(timeout=3.0, follow_redirects=True, verify=True) as client:
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

    @staticmethod
    def extract_page_data(html: str, base_url: str) -> Dict[str, Any]:
        """Parses HTML into clean readable text, title, and all outgoing <a href> links."""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        title = re.sub(r"&[a-zA-Z0-9#]+;", " ", title)

        raw_links = re.findall(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        valid_links = []
        ignored_extensions = (
            ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz",
            ".mp4", ".mp3", ".svg", ".css", ".js", ".ico", ".woff", ".woff2"
        )

        for l in raw_links:
            try:
                full_url = urljoin(base_url, l.strip())
                parsed = urlparse(full_url)
                if parsed.scheme in ("http", "https"):
                    path_lower = parsed.path.lower()
                    if not any(path_lower.endswith(ext) for ext in ignored_extensions):
                        if not any(sub in path_lower for sub in ("/action=edit", "/special:", "/user:", "/file:")):
                            valid_links.append(full_url)
            except Exception:
                pass

        cleaned = re.sub(
            r"<(script|style|noscript|svg|nav|footer|header|aside)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"<[^>]+>", " ", cleaned)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "title": title or "Web Document",
            "text": text,
            "outlinks": list(dict.fromkeys(valid_links))[:50],
        }

    async def fetch_and_index(self, url: str, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
        """Politely fetches a URL directly, indexes into Base128, and enqueues outlinks."""
        norm_url = self._normalize_url(url)
        self.visited.add(norm_url)
        self.current_crawling_url = url
        domain = self._get_domain(url)

        # 1. Robots.txt Compliance Check
        if not await self.is_allowed_by_robots(url):
            print(f"[PureSpider] Disallowed by robots.txt: {url}")
            return None

        # 2. Dynamic Domain Rate Limiting Delay
        await self._enforce_domain_delay(domain)

        req_start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=True) as client:
                res = await client.get(url, headers=self.headers)
                latency = time.time() - req_start

                # Adaptive delay: if server is slow, increase delay slightly; if fast, recover backoff
                if latency > 2.5:
                    self.domain_delays[domain] = min(10.0, self.domain_delays.get(domain, 1.0) + 0.5)
                elif latency < 0.8:
                    self.domain_backoff[domain] = max(1.0, self.domain_backoff.get(domain, 1.0) * 0.9)

                # HTTP 429 Too Many Requests / 503 Service Unavailable -> Back off exponentially!
                if res.status_code in (429, 503):
                    retry_after = res.headers.get("retry-after")
                    if retry_after and retry_after.isdigit():
                        backoff_seconds = float(retry_after)
                    else:
                        backoff_seconds = min(60.0, self.domain_delays.get(domain, 1.0) * 2.5)

                    self.domain_delays[domain] = backoff_seconds
                    self.domain_backoff[domain] = min(16.0, self.domain_backoff.get(domain, 1.0) * 2.0)
                    print(f"[PureSpider] Rate-limited (HTTP {res.status_code}) on {domain}. Backing off {backoff_seconds:.1f}s.")
                    # Re-queue for later
                    if len(self.frontier) < 2000:
                        self.frontier.append(url)
                    return None

                content_type = res.headers.get("content-type", "").lower()
                if res.status_code == 200 and ("text/html" in content_type or "text/plain" in content_type):
                    data = self.extract_page_data(res.text, str(res.url))
                    if len(data["text"]) > 80:
                        frontier_set = set(self.frontier)
                        for link in data["outlinks"]:
                            norm_link = self._normalize_url(link)
                            if norm_link not in frontier_set and norm_link not in self.visited and len(self.frontier) < 2000:
                                self.frontier.append(link)
                                frontier_set.add(norm_link)

                        doc_id = self.store.add_document(
                            url=str(res.url),
                            title=data["title"],
                            content=data["text"][:16000],
                            snippet=data["text"][:260] + "...",
                            source="autonomous_spider",
                        )
                        self.pages_crawled_session += 1
                        self._save_state()
                        return self.store.catalog.get(doc_id)
                else:
                    print(f"[PureSpider] Skip HTTP {res.status_code} for {res.url}")
        except httpx.HTTPError as e:
            print(f"[PureSpider] HTTP error on {url}: {e}")
        except Exception as e:
            print(f"[PureSpider] Error on {url}: {e}")
        finally:
            self.current_crawling_url = ""

        return None

    async def crawl_step(self, count: int = 1) -> List[Dict[str, Any]]:
        """Pops unvisited URLs from frontier and crawls them."""
        indexed = []
        while self.frontier and len(indexed) < count:
            url = self.frontier.pop(0)
            norm = self._normalize_url(url)
            if norm in self.visited:
                continue
            doc = await self.fetch_and_index(url)
            if doc:
                indexed.append(doc)
        return indexed

    async def run_crawler_loop(self):
        """Continuous background crawl loop following hyperlinks with dynamic delays."""
        self.is_running = True
        print(f"[PureSpider] Autonomous hyperlink crawler started. Initial frontier: {len(self.frontier)} links.")
        while self.is_running:
            if not self.frontier:
                for s in DEFAULT_SEEDS:
                    if self._normalize_url(s) not in self.visited:
                        self.frontier.append(s)

            try:
                await self.crawl_step(count=1)
            except Exception as e:
                print(f"[PureSpider] Error: {e}")
            await asyncio.sleep(self.default_crawl_delay)

    def start_background(self):
        """Starts background crawler loop if not running."""
        if not self.is_running or self.crawler_task is None or self.crawler_task.done():
            self.is_running = True
            self.crawler_task = asyncio.create_task(self.run_crawler_loop())

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
            "current_crawling_url": self.current_crawling_url,
            "crawl_delay_seconds": self.default_crawl_delay,
            "active_domains_tracked": len(self.domain_delays),
        }
