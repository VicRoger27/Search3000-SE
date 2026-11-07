"""On-Disk Inverted Index and Document Store for Search3000.

All indexed web documents, inverted index postings, and metadata catalogs
are persisted in Base128 format inside:
`data/indexed_sites_base128/`
"""

import hashlib
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine.storage.base128 import Base128Codec


class DiskIndexStore:
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            # Default to <workspace_root>/data/indexed_sites_base128
            self.base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "indexed_sites_base128"
        else:
            self.base_dir = Path(base_dir)

        self.docs_dir = self.base_dir / "docs"
        self.catalog_file = self.base_dir / "catalog.b128"
        self.postings_file = self.base_dir / "postings.b128"

        self._ensure_directories()
        self.catalog: Dict[str, Dict[str, Any]] = {}
        self.postings: Dict[str, List[Tuple[str, int]]] = {}
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_len: float = 0.0

        self.load_index()

    def _ensure_directories(self):
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Lowercases and extracts clean alphanumeric tokens from text."""
        return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-\u00C0-\u017F]+\b", text)]

    @staticmethod
    def hash_url(url: str) -> str:
        """Computes a deterministic hash ID for a URL."""
        return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()[:16]

    def load_index(self):
        """Loads catalog and postings from Base128 disk files if they exist."""
        if self.catalog_file.exists():
            try:
                data = self.catalog_file.read_bytes()
                loaded = Base128Codec.deserialize_payload(data)
                if isinstance(loaded, dict):
                    self.catalog = loaded
            except Exception as e:
                print(f"[DiskIndexStore] Warning loading catalog: {e}")

        if self.postings_file.exists():
            try:
                data = self.postings_file.read_bytes()
                loaded = Base128Codec.deserialize_payload(data)
                if isinstance(loaded, dict):
                    # Tuple list restoration
                    self.postings = {k: [tuple(p) for p in v] for k, v in loaded.items()}
            except Exception as e:
                print(f"[DiskIndexStore] Warning loading postings: {e}")

        self._recalculate_stats()

    def save_index(self):
        """Persists catalog and inverted postings to Base128 files on disk."""
        self._ensure_directories()
        try:
            catalog_payload = Base128Codec.serialize_payload(self.catalog)
            self.catalog_file.write_bytes(catalog_payload)

            postings_payload = Base128Codec.serialize_payload(self.postings)
            self.postings_file.write_bytes(postings_payload)
        except Exception as e:
            print(f"[DiskIndexStore] Error saving index: {e}")

    def _recalculate_stats(self):
        self.doc_lengths = {doc_id: meta.get("word_count", 0) for doc_id, meta in self.catalog.items()}
        total_len = sum(self.doc_lengths.values())
        total_docs = len(self.catalog)
        self.avg_doc_len = (total_len / total_docs) if total_docs > 0 else 1.0

    def add_document(
        self,
        url: str,
        title: str,
        content: str,
        snippet: str = "",
        tags: Optional[List[str]] = None,
        sparkx_summary: str = "",
        source: str = "web",
    ) -> str:
        """Indexes a web page into Base128 disk files and updates the inverted index."""
        doc_id = self.hash_url(url)
        tokens = self.tokenize(f"{title} {content} {' '.join(tags or [])}")
        word_count = len(tokens)

        # Count frequencies
        tf_map: Dict[str, int] = {}
        for token in tokens:
            tf_map[token] = tf_map.get(token, 0) + 1

        # Document record saved to Base128 file
        doc_record = {
            "doc_id": doc_id,
            "url": url,
            "title": title,
            "snippet": snippet or (content[:240] + ("..." if len(content) > 240 else "")),
            "content": content,
            "tags": tags or [],
            "sparkx_summary": sparkx_summary,
            "source": source,
            "word_count": word_count,
            "indexed_at": time.time(),
        }

        doc_path = self.docs_dir / f"{doc_id}.b128"
        doc_path.write_bytes(Base128Codec.serialize_payload(doc_record))

        # Update metadata catalog
        self.catalog[doc_id] = {
            "doc_id": doc_id,
            "url": url,
            "title": title,
            "snippet": doc_record["snippet"],
            "tags": tags or [],
            "sparkx_summary": sparkx_summary,
            "source": source,
            "word_count": word_count,
            "indexed_at": doc_record["indexed_at"],
        }

        # Update postings
        for token, count in tf_map.items():
            if token not in self.postings:
                self.postings[token] = []
            # Remove prior entry if exists
            self.postings[token] = [p for p in self.postings[token] if p[0] != doc_id]
            self.postings[token].append((doc_id, count))

        self._recalculate_stats()
        self.save_index()
        return doc_id

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves and deserializes full document payload from its Base128 disk file."""
        doc_path = self.docs_dir / f"{doc_id}.b128"
        if not doc_path.exists():
            return None
        try:
            return Base128Codec.deserialize_payload(doc_path.read_bytes())
        except Exception:
            return None

    def search_bm25(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """Performs Okapi BM25 ranked search across all indexed sites."""
        query_tokens = self.tokenize(query)
        if not query_tokens or not self.catalog:
            return []

        k1 = 1.5
        b = 0.75
        N = len(self.catalog)
        scores: Dict[str, float] = {}

        for token in query_tokens:
            if token not in self.postings:
                # Check for prefix match
                matched_tokens = [t for t in self.postings.keys() if t.startswith(token) and len(t) <= len(token) + 3]
            else:
                matched_tokens = [token]

            for m_token in matched_tokens:
                postings_list = self.postings[m_token]
                n_t = len(postings_list)
                # Standard BM25 IDF
                idf = math.log(1.0 + (N - n_t + 0.5) / (n_t + 0.5))

                for doc_id, tf in postings_list:
                    doc_len = self.doc_lengths.get(doc_id, self.avg_doc_len)
                    numerator = tf * (k1 + 1.0)
                    denominator = tf + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len))
                    term_score = idf * (numerator / denominator)
                    scores[doc_id] = scores.get(doc_id, 0.0) + term_score

        # Rank documents
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in ranked:
            meta = self.catalog.get(doc_id)
            if not meta:
                continue

            # Create highlighted snippet
            snippet = self._generate_highlighted_snippet(meta["snippet"], query_tokens)
            results.append({
                "doc_id": doc_id,
                "url": meta["url"],
                "title": meta["title"],
                "snippet": snippet,
                "tags": meta.get("tags", []),
                "sparkx_summary": meta.get("sparkx_summary", ""),
                "score": round(score, 4),
                "indexed_at": meta.get("indexed_at", 0),
            })

        return results

    def _generate_highlighted_snippet(self, text: str, query_tokens: List[str]) -> str:
        """Wraps matched keywords in bold tags for Google-style results preview."""
        if not text:
            return ""
        pattern = re.compile(rf"\b({'|'.join(re.escape(t) for t in query_tokens)})\b", re.IGNORECASE)
        return pattern.sub(r"<b>\1</b>", text)

    def get_stats(self) -> Dict[str, Any]:
        """Calculates total disk usage and statistics for the Base128 directory."""
        total_bytes = 0
        file_count = 0
        if self.base_dir.exists():
            for p in self.base_dir.rglob("*.b128"):
                total_bytes += p.stat().st_size
                file_count += 1

        return {
            "total_documents": len(self.catalog),
            "total_vocabulary_terms": len(self.postings),
            "base128_files_count": file_count,
            "base128_disk_bytes": total_bytes,
            "base128_disk_formatted": f"{total_bytes / (1024 * 1024):.2f} MB" if total_bytes > 1024*1024 else f"{total_bytes / 1024:.1f} KB",
            "base128_folder_path": str(self.base_dir),
        }
