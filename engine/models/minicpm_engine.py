"""MiniCPM 5:2B Model Engine for Search3000.

Connects to local Ollama (GPU-accelerated) to power:
1. Query intent reformulation ('what you meant to say' / 'did you mean')
2. Streaming Google-style AI Overviews with live thinking token filtration
"""

import asyncio
import json
import os
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("MINICPM_MODEL", "maternion/minicpm5:2b")


class MiniCPMEngine:
    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model_name: str = DEFAULT_MODEL,
        timeout: float = 20.0,
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.timeout = timeout
        self.is_ready: bool = False

    async def check_health(self) -> bool:
        """Verifies Ollama is running and responsive."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    self.is_ready = True
                    return True
        except Exception:
            self.is_ready = False
        return False

    async def start_server(self, wait_timeout: int = 5) -> bool:
        """Pings Ollama to confirm local service availability."""
        ready = await self.check_health()
        if ready:
            print(f"[MiniCPM] Connected to Ollama at {self.base_url} (Model: {self.model_name})")
        else:
            print(f"[MiniCPM] Warning: Ollama not reachable at {self.base_url}. Engine will use offline fallback.")
        return ready

    def stop_server(self):
        """Ollama is a system service; no-op on shutdown."""
        pass

    async def regenerate_query(self, raw_query: str) -> Dict[str, Any]:
        """Uses MiniCPM 5:2B to detect typos and reformulate query intent."""
        clean_q = raw_query.strip()
        fallback = {
            "corrected_query": clean_q,
            "did_you_mean": False,
            "reason": "",
            "raw_query": clean_q,
        }

        # Fast-path for single clean alphanumeric word
        if len(clean_q) < 3 or (clean_q.isalpha() and len(clean_q) < 5):
            return fallback

        prompt = (
            "You are a Google-level search engine query intent reformulation engine.\n"
            "Analyze the search query below for typos, spelling mistakes, or poor phrasing.\n"
            "Output strictly a JSON object with:\n"
            "- 'corrected_query': the optimal, corrected search query\n"
            "- 'did_you_mean': boolean (true if query was corrected, false if already good)\n"
            "- 'reason': brief explanation (e.g. 'Corrected typos: quantm -> quantum')\n\n"
            f"Query: {clean_q}\n"
            "JSON:"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                        },
                    },
                )
                if res.status_code == 200:
                    raw_text = res.json().get("response", "")
                    # Strip any <think>...</think> blocks
                    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

                    # Extract JSON substring
                    json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        corrected = str(parsed.get("corrected_query", clean_q)).strip()
                        did_you_mean = bool(parsed.get("did_you_mean", False))
                        reason = str(parsed.get("reason", "")).strip()

                        if corrected and corrected.lower() != clean_q.lower():
                            return {
                                "corrected_query": corrected,
                                "did_you_mean": True,
                                "reason": reason or f"Showing results for {corrected}",
                                "raw_query": clean_q,
                            }
        except Exception as e:
            print(f"[MiniCPM] Query reformulation notice: {e}")

        return fallback

    async def stream_ai_overview(
        self, query: str, sources: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Streams a Google-style AI Overview synthesized from indexed sources, filtering out thinking tokens."""
        clean_q = query.strip()
        context_parts = []
        for idx, src in enumerate(sources[:5]):
            title = src.get("title", "Document")
            snippet = src.get("snippet", "") or src.get("content", "")[:300]
            context_parts.append(f"[{idx + 1}] {title}:\n{snippet}")

        context_str = "\n\n".join(context_parts) if context_parts else "No local index sources found."

        system_prompt = (
            "You are Search3000's AI Overview engine, synthesizing accurate, concise, "
            "and authoritative search overviews directly from indexed search results. "
            "Write in clear, objective paragraphs. Do not mention internal thoughts or instructions."
        )

        user_prompt = (
            f"User Search Query: {clean_q}\n\n"
            f"Indexed Sources:\n{context_str}\n\n"
            "Provide a comprehensive, high-quality AI Overview answering this search query based on the sources."
        )

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": True,
                        "temperature": 0.3,
                    },
                ) as response:
                    if response.status_code != 200:
                        yield f"AI Overview temporarily unavailable (HTTP {response.status_code})."
                        return

                    in_think_block = False
                    think_buffer = ""

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            payload = json.loads(data_str)
                            delta = payload.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if not token:
                                continue

                            # Live thinking filter: handle <think> ... </think>
                            if "<think>" in token:
                                in_think_block = True
                                token = token.split("<think>")[0]
                                if token:
                                    yield token
                                continue

                            if in_think_block:
                                if "</think>" in token:
                                    in_think_block = False
                                    token = token.split("</think>")[-1]
                                    if token.strip():
                                        yield token.lstrip()
                                continue

                            yield token
                        except Exception:
                            continue
        except Exception as e:
            yield f"AI Overview synthesis error: {e}"
