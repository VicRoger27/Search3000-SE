"""Live-Fetch Web Crawler and Content Extractor for Search3000.

Fetches live web pages matching incoming queries and seeds, parses and cleans HTML,
and commits them directly to the permanent Base128 disk index (`data/indexed_sites_base128/`).
"""

import asyncio
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from duckduckgo_search import DDGS

from engine.storage.disk_index import DiskIndexStore


class LiveCrawler:
    def __init__(self, store: DiskIndexStore):
        self.store = store
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36 Search3000Bot/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    @staticmethod
    def clean_html(html: str) -> Dict[str, str]:
        """Strips HTML boilerplate, scripts, styles, and extracts title, description, and clean text."""
        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        # Clean title of HTML entities
        title = re.sub(r"&[a-zA-Z0-9#]+;", " ", title)

        # Remove scripts, styles, noscript, svg, header, footer, nav
        cleaned = re.sub(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", " ", cleaned)
        
        # Decode entities and normalize whitespaces
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "title": title or "Web Document",
            "text": text,
        }

    async def fetch_page(self, url: str, timeout: float = 6.0) -> Optional[Dict[str, str]]:
        """Asynchronously fetches and extracts readable content from a URL."""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "").lower():
                    extracted = self.clean_html(resp.text)
                    return {
                        "url": str(resp.url),
                        "title": extracted["title"],
                        "content": extracted["text"][:10000],  # Top 10KB clean text
                    }
        except Exception:
            pass
        return None

    def search_live_web(self, query: str, max_results: int = 8) -> List[Dict[str, str]]:
        """Queries DuckDuckGo search to discover live relevant URLs."""
        results = []
        try:
            with DDGS() as ddgs:
                # Use backend='lite' for ultra-reliable web results without bot challenges
                ddg_results = ddgs.text(query, max_results=max_results, backend="lite")
                for r in ddg_results:
                    results.append({
                        "url": r.get("href", ""),
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                    })
        except Exception as e:
            try:
                # Fallback to default backend
                with DDGS() as ddgs:
                    ddg_results = ddgs.text(query, max_results=max_results)
                    for r in ddg_results:
                        results.append({
                            "url": r.get("href", ""),
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                        })
            except Exception as e2:
                print(f"[LiveCrawler] Live web discovery notice: {e2}")
        return results

    async def fetch_and_index_query(
        self, query: str, max_fetch: int = 6
    ) -> List[Dict[str, Any]]:
        """Discovers live web pages for the query, scrapes them, and commits to Base128 disk store."""
        live_hits = self.search_live_web(query, max_results=max_fetch)
        if not live_hits:
            return []

        tasks = []
        for hit in live_hits:
            url = hit["url"]
            if not url or not url.startswith("http"):
                continue
            # Check if already indexed recently
            doc_id = self.store.hash_url(url)
            if doc_id in self.store.catalog:
                continue
            tasks.append(self.fetch_page(url))

        fetched_pages = await asyncio.gather(*tasks, return_exceptions=True)

        indexed_docs = []
        for i, res in enumerate(fetched_pages):
            if isinstance(res, dict) and res.get("content"):
                url = res["url"]
                title = res["title"] or live_hits[i].get("title", url)
                snippet = live_hits[i].get("snippet") or res["content"][:240]
                
                # Commit to Base128 disk store
                doc_id = self.store.add_document(
                    url=url,
                    title=title,
                    content=res["content"],
                    snippet=snippet,
                    source="live_crawl",
                )
                indexed_docs.append(self.store.catalog[doc_id])
            elif i < len(live_hits):
                # Fallback: if direct fetch was blocked by bot-protection, index the verified snippet
                hit = live_hits[i]
                if hit.get("url") and hit.get("snippet"):
                    doc_id = self.store.add_document(
                        url=hit["url"],
                        title=hit.get("title", "Web Page"),
                        content=f"{hit.get('title', '')}. {hit.get('snippet', '')}",
                        snippet=hit.get("snippet", ""),
                        source="live_snippet",
                    )
                    indexed_docs.append(self.store.catalog[doc_id])

        return indexed_docs

    async def index_custom_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Explicitly indexes a user-specified URL into the Base128 database."""
        page = await self.fetch_page(url)
        if not page:
            return None

        doc_id = self.store.add_document(
            url=page["url"],
            title=page["title"],
            content=page["content"],
            snippet=page["content"][:240] + "...",
            source="manual_entry",
        )
        return self.store.catalog.get(doc_id)
