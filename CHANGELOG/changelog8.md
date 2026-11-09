# Changelog 8: Quality Gates Hardening & Test Coverage

### Added & Refined
- **Comprehensive API Endpoint Test Coverage (`tests/test_api.py`)**:
  - Implemented 10 unit tests with FastAPI `TestClient` covering root `/` HTML delivery, `/api/index/stats`, `/api/spider/status`, `/api/spider/toggle`, input sanitization of control characters, query length limit validation (300 chars), filter parameter whitelist fallback, and streaming SSE AI Overview (`/api/ai/stream`).
  - Caught and fixed asynchronous concurrency bug in `/api/spider/toggle` by converting route to `async def` and guarding `start_background()` event loop attachment.
- **Main Launcher Test Suite (`tests/test_run.py`)**:
  - Implemented unit tests for `terminate_prior_instances`, `seed_foundational_index` idempotency, and launcher constants in `run.py`.
- **Environment Path Portability (`engine/models/sparkx_engine.py`)**:
  - Made `DEFAULT_MODEL_PATH` and `DEFAULT_SERVER_BIN` configurable via `SPARKX_MODEL_PATH` and `LLAMA_SERVER_BIN` environment variables with local fallbacks.
- **Audit Script Overhaul (`audit_manual.py`)**:
  - Corrected directory resolution from `parent.parent` to `parent`, fixed path resolution relative to `project_path`, and cleaned console status indicators to achieve 100% score (17/17 passed).
- **Bytecode Artifact Hygiene (`.gitignore`)**:
  - Expanded `.gitignore` with recursive `**/__pycache__/` and `*.py[cod]` patterns and purged all lingering bytecode artifacts.
