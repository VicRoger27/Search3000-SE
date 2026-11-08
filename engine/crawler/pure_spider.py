"""Pure Hyperlink Graph Web Spider for Search3000.

Operates as a 100% independent web crawler following hyperlinks across the web graph:
- ZERO reliance on external search engines (no Google, no Bing, no DuckDuckGo).
- ZERO search APIs or OpenSearch endpoints.
- Pure hyperlink traversal: fetches seed pages, extracts <a href="..."> outlinks,
  normalizes them into an on-disk frontier, and commits parsed documents to Base128.
"""

import asyncio
import os
import re
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
        self.crawl_delay: float = 1.0

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
            except Exception:
                pass

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
        except Exception:
            pass

    @staticmethod
    def extract_page_data(html: str, base_url: str) -> Dict[str, Any]:
        """Parses HTML into clean readable text, title, and all outgoing <a href> links."""
        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        title = re.sub(r"&[a-zA-Z0-9#]+;", " ", title)

        # Extract all outgoing hyperlinks
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
                        # Filter out internal anchor jumps and edit pages
                        if not any(sub in path_lower for sub in ("/action=edit", "/special:", "/user:", "/file:")):
                            valid_links.append(full_url)
            except Exception:
                pass

        # Clean text
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
            "outlinks": list(dict.fromkeys(valid_links))[:50],  # Unique top 50 outlinks
        }

    async def fetch_and_index(self, url: str, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
        """Fetches a URL directly, indexes into Base128, and enqueues outlinks."""
        norm_url = self._normalize_url(url)
        self.visited.add(norm_url)
        self.current_crawling_url = url

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=True) as client:
                res = await client.get(url, headers=self.headers)
                content_type = res.headers.get("content-type", "").lower()
                if res.status_code == 200 and ("text/html" in content_type or "text/plain" in content_type):
                    data = self.extract_page_data(res.text, str(res.url))
                    if len(data["text"]) > 80:
                        # Enqueue outlinks using set for O(1) lookup
                        frontier_set = set(self.frontier)
                        for link in data["outlinks"]:
                            norm_link = self._normalize_url(link)
                            if norm_link not in frontier_set and len(self.frontier) < 2000:
                                self.frontier.append(link)
                                frontier_set.add(norm_link)

                        # Commit document to Base128 on-disk store
                        doc_id = self.store.add_document(
                            url=str(res.url),
                            title=data["title"],
                            content=data["text"][:16000],  # Up to 16KB text
                            snippet=data["text"][:260] + "...",
                            source="autonomous_spider",
                        )
                        self.pages_crawled_session += 1
                        self._save_state()
                        return self.store.catalog.get(doc_id)
                else:
                    print(f"[PureSpider] Skip {res.status_code} {res.url}")
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
            await asyncio.sleep(self.crawl_delay)
        return indexed

    async def run_crawler_loop(self):
        """Continuous background crawl loop following hyperlinks."""
        self.is_running = True
        print(f"[PureSpider] Autonomous hyperlink crawler started. Initial frontier: {len(self.frontier)} links.")
        while self.is_running:
            if not self.frontier:
                # Re-seed if exhausted
                for s in DEFAULT_SEEDS:
                    if self._normalize_url(s) not in self.visited:
                        self.frontier.append(s)

            try:
                await self.crawl_step(count=1)
            except Exception as e:
                print(f"[PureSpider] Error: {e}")
            await asyncio.sleep(self.crawl_delay)

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
            "crawl_delay_seconds": self.crawl_delay,
        }
