"""Spark-X 2.6 1.7B Model Engine for Search3000.

Powers query intent reformulation ('what you meant to say'),
indexing content analysis, and streaming Google AI Overviews using
a dedicated llama-server instance running on the NVIDIA RTX 5060 Ti GPU.
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

DEFAULT_MODEL_PATH = (
    r"C:\Users\Victor\.cache\huggingface\hub\models--XHToken--Spark-X2.6-1.7B-GGUF"
    r"\snapshots\3c90a598d4e4a030703080b5f278fe098247fbef\Spark-X2.6-1.7B-Q8_0.gguf"
)

DEFAULT_SERVER_BIN = r"C:\Users\Victor\AppData\Local\hermes\tools\llamacpp-cuda-11671-win32-x64\llama-server.exe"
FALLBACK_SERVER_BIN = "llama-server"


class SparkXEngine:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        server_bin: str = DEFAULT_SERVER_BIN,
        port: int = 8085,
        host: str = "127.0.0.1",
        ngl: int = 99,
        ctx_size: int = 4096,
    ):
        self.model_path = model_path
        self.server_bin = server_bin
        self.port = port
        self.host = host
        self.ngl = ngl
        self.ctx_size = ctx_size
        self.base_url = f"http://{host}:{port}"
        self.process: Optional[subprocess.Popen] = None

    def find_executable(self) -> str:
        """Finds the best available llama-server executable with CUDA support."""
        if Path(self.server_bin).exists():
            return self.server_bin
        return FALLBACK_SERVER_BIN

    def terminate_existing_instance(self):
        """Kills any active llama-server process bound to this port per user rules."""
        try:
            # Query and kill processes listening on our specific port
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {self.port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        except Exception:
            pass

    async def is_server_ready(self) -> bool:
        """Checks if llama-server is responding to health requests."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def start_server(self, wait_timeout: int = 25):
        """Spawns the llama-server subprocess offloaded to GPU."""
        if await self.is_server_ready():
            print(f"[SparkXEngine] Server already responding on {self.base_url}")
            return

        self.terminate_existing_instance()
        exe = self.find_executable()

        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Spark-X model not found at {self.model_path}")

        args = [
            exe,
            "-m", self.model_path,
            "-ngl", str(self.ngl),
            "-c", str(self.ctx_size),
            "--port", str(self.port),
            "--host", self.host,
            "--no-warmup",
            "--jinja",
        ]

        print(f"[SparkXEngine] Starting llama-server on GPU port {self.port}...")
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            if await self.is_server_ready():
                print(f"[SparkXEngine] Spark-X 2.6 is live and ready on GPU at {self.base_url}")
                return
            await asyncio.sleep(0.5)

        raise TimeoutError("[SparkXEngine] Timed out waiting for llama-server to start.")

    def stop_server(self):
        """Cleanly stops the llama-server subprocess."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
        self.terminate_existing_instance()

    async def regenerate_query(self, raw_query: str) -> Dict[str, Any]:
        """Uses Spark-X to reformulate the user's raw query into the intended search string.
        
        Fixes typos, spelling mistakes, phonetic mixups, and restores search keywords.
        """
        raw_query = raw_query.strip()
        if not raw_query:
            return {"corrected_query": "", "did_you_mean": False, "reason": ""}

        prompt = (
            "You are Search3000's query intent reformer. Correct typos, spelling errors, abbreviations, and restore search intent.\n"
            "Raw: quantm computng suprcondctr\n"
            "Corrected: quantum computing superconductor\n\n"
            "Raw: deepseck vs chatgpt artifcl intlgnce\n"
            "Corrected: deepseek vs chatgpt artificial intelligence\n\n"
            "Raw: james webb telscop exoplant\n"
            "Corrected: james webb telescope exoplanet\n\n"
            "Raw: pythn fastpi tutrial\n"
            "Corrected: python fastapi tutorial\n\n"
            f"Raw: {raw_query}\n"
            "Corrected:"
        )

        payload = {
            "prompt": prompt,
            "temperature": 0.0,
            "max_tokens": 40,
            "stop": ["\n", "Raw:"],
        }

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(f"{self.base_url}/v1/completions", json=payload)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["text"].strip()
                    # Clean up punctuation
                    cleaned = text.strip("\"'.,")
                    is_different = cleaned.lower() != raw_query.lower()
                    return {
                        "corrected_query": cleaned if is_different else raw_query,
                        "did_you_mean": is_different,
                        "reason": f"Corrected search terms for '{raw_query}'" if is_different else "",
                        "raw_query": raw_query,
                    }
        except Exception as e:
            print(f"[SparkXEngine] Query reformulation fallback: {e}")

        return {
            "corrected_query": raw_query,
            "did_you_mean": False,
            "reason": "Fallback: passed through original query.",
            "raw_query": raw_query,
        }

    async def summarize_page(self, title: str, content: str) -> Dict[str, Any]:
        """Extracts a dense summary and top search keywords for disk indexing."""
        sample_text = content[:1500]
        prompt = (
            f"Title: {title}\n"
            f"Content: {sample_text}\n\n"
            "Provide a 2-sentence summary and 5 key search terms. "
            "Output ONLY valid JSON with keys 'summary' (string) and 'keywords' (list of strings)."
        )

        payload = {
            "model": "Spark-X2.6-1.7B-Q8_0",
            "messages": [
                {"role": "system", "content": "You are a web indexer assistant. Output strictly valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                if res.status_code == 200:
                    return json.loads(res.json()["choices"][0]["message"]["content"])
        except Exception:
            pass

        return {"summary": sample_text[:180] + "...", "keywords": []}

    async def stream_ai_overview(
        self, query: str, search_results: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Streams a Perplexity / Google AI Overviews synthesis with citations."""
        # Format sources
        sources_text = ""
        for i, doc in enumerate(search_results[:5], 1):
            snippet = doc.get("snippet", "").replace("<b>", "").replace("</b>", "")
            title = doc.get("title", "Web Page")
            sources_text += f"[{i}] {title}\nSummary/Snippet: {snippet}\n\n"

        system_prompt = (
            "You are Search3000's AI Overview engine. "
            "Synthesize a clear, direct, and comprehensive answer to the user's query based on the provided search results. "
            "Use inline numerical citations like [1], [2] when referencing information from the sources. "
            "Format your answer cleanly with markdown bullet points or paragraphs where appropriate. "
            "Be objective, factual, and concise."
        )

        user_content = (
            f"User Query: {query}\n\n"
            f"Search Sources:\n{sources_text}\n"
            "Synthesize an AI Overview answering the query based on these sources with citations."
        )

        payload = {
            "model": "Spark-X2.6-1.7B-Q8_0",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 800,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=payload) as response:
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception as e:
            yield f"\n[AI Overview Error: {str(e)}]"
