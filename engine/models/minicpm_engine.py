"""MiniCPM 5:2B GPU Engine for Search3000 (Pure llama.cpp - Zero Ollama).

Powers sub-100ms query intent reformulation and real-time streaming AI Overviews
directly using llama-server on NVIDIA RTX 5060 Ti with 100% GPU offloading.
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

DEFAULT_MODEL_PATH = os.getenv(
    "MINICPM_MODEL_PATH",
    r"C:\Users\Victor\AppData\Local\hermes\models\MiniCPM5-2B-Q4_K_M.gguf",
)

DEFAULT_SERVER_BIN = os.getenv(
    "LLAMA_SERVER_BIN",
    r"C:\Users\Victor\AppData\Local\hermes\tools\llamacpp-cuda-11671-win32-x64\llama-server.exe",
)


class MiniCPMEngine:
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
        self.is_ready: bool = False

    def find_executable(self) -> str:
        if os.path.exists(self.server_bin):
            return self.server_bin
        return "llama-server"

    async def check_health(self) -> bool:
        """Pings the llama-server health check endpoint."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(f"{self.base_url}/health")
                if res.status_code == 200:
                    self.is_ready = True
                    return True
        except Exception:
            self.is_ready = False
        return False

    async def start_server(self, wait_timeout: int = 25) -> bool:
        """Boots llama-server on GPU if not already active."""
        if await self.check_health():
            print(f"[MiniCPM] Server is already running and healthy on {self.base_url}")
            return True

        exe = self.find_executable()
        cmd = [
            exe,
            "-m", self.model_path,
            "--port", str(self.port),
            "--host", self.host,
            "-ngl", str(self.ngl),
            "-c", str(self.ctx_size),
            "--no-reasoning-preserve",
        ]

        print(f"[MiniCPM] Launching llama-server on RTX 5060 Ti GPU: {exe}")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            print(f"[MiniCPM] Warning: Could not launch llama-server: {e}")
            return False

        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            if await self.check_health():
                print(f"[MiniCPM] MiniCPM 5:2B successfully loaded on {self.base_url} (GPU Layers: {self.ngl})")
                return True
            await asyncio.sleep(0.5)

        print("[MiniCPM] Warning: Server startup timeout reached. Offline fallbacks active.")
        return False

    def stop_server(self):
        """Clean shutdown of the server process."""
        if self.process:
            print("[MiniCPM] Stopping llama-server...")
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
            self.is_ready = False

    async def regenerate_query(self, raw_query: str) -> Dict[str, Any]:
        """Sub-100ms few-shot query intent reformulation using fast completion."""
        clean_q = raw_query.strip()
        fallback = {
            "corrected_query": clean_q,
            "did_you_mean": False,
            "reason": "",
            "raw_query": clean_q,
        }

        if len(clean_q) < 3 or (clean_q.isalpha() and len(clean_q) < 5):
            return fallback

        prompt = (
            "Task: Correct typos and spelling errors in search queries into standard English search terms.\n\n"
            "Input: deep leanning pytrch\n"
            "Output: deep learning pytorch\n\n"
            "Input: cmputer vison transfrmer\n"
            "Output: computer vision transformer\n\n"
            "Input: quantm computng suprcondctr\n"
            "Output: quantum computing superconductor\n\n"
            "Input: yolo vs sm objct detct\n"
            "Output: yolo vs sam object detection\n\n"
            f"Input: {clean_q}\n"
            "Output:"
        )

        try:
            async with httpx.AsyncClient(timeout=1.8) as client:
                res = await client.post(
                    f"{self.base_url}/v1/completions",
                    json={
                        "prompt": prompt,
                        "max_tokens": 24,
                        "temperature": 0.05,
                        "stop": ["\n", "Input:"],
                    },
                )
                if res.status_code == 200:
                    text = res.json()["choices"][0]["text"].strip()
                    # Filter out quotes or stray punctuation
                    text = text.strip('"\' ')
                    if text and text.lower() != clean_q.lower() and len(text) > 2:
                        return {
                            "corrected_query": text,
                            "did_you_mean": True,
                            "reason": f"Corrected typos in '{clean_q}'",
                            "raw_query": clean_q,
                        }
        except Exception:
            pass

        return fallback

    async def stream_ai_overview(
        self, query: str, sources: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Streams a Perplexity/Google-style AI Overview synthesized in milliseconds."""
        clean_q = query.strip()
        context_parts = []
        for idx, src in enumerate(sources[:5]):
            title = src.get("title", "Document")
            snippet = src.get("snippet", "") or src.get("content", "")[:260]
            context_parts.append(f"[{idx + 1}] {title}: {snippet}")

        context_str = "\n".join(context_parts) if context_parts else "No local index sources found."

        prompt = (
            "You are Search3000's lightning AI Search Overview engine.\n"
            "Synthesize a clear, authoritative, 2-3 paragraph answer to the search query using the indexed sources below.\n"
            "Cite sources like [1] or [2] where appropriate. Be concise, direct, and factual.\n\n"
            f"Indexed Sources:\n{context_str}\n\n"
            f"User Search Query: {clean_q}\n"
            "AI Overview:"
        )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/completions",
                    json={
                        "prompt": prompt,
                        "max_tokens": 360,
                        "temperature": 0.2,
                        "stream": True,
                        "stop": ["User Search Query:", "Indexed Sources:"],
                    },
                ) as response:
                    if response.status_code != 200:
                        yield f"AI Overview temporarily offline (HTTP {response.status_code})."
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            payload = json.loads(data_str)
                            token = payload.get("choices", [{}])[0].get("text", "")
                            if token:
                                yield token
                        except Exception:
                            continue
        except Exception as e:
            yield f"AI Overview ready once GPU server is initialized."
