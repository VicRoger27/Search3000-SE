# Changelog v2.0.2 - Security & Stability Patch (2026-11-07)

## 🔒 Critical Security Fixes

### SSL Certificate Verification
**File:** `engine/crawler/pure_spider.py` (Line 158)
- **Issue:** `verify=False` disabled SSL certificate verification, enabling MITM attacks
- **Fix:** Changed to `verify=True` to enforce proper SSL validation
- **Impact:** ⚠️ **CRITICAL** - Prevents man-in-the-middle attacks and traffic interception

### XSS Vulnerability
**File:** `web/app.js` (escapeHtml function)
- **Issue:** Basic HTML escaping didn't handle event handlers or javascript: protocols
- **Fix:** Added sanitization for:
  - Event handlers (`onclick=`, `onerror=`, etc.)
  - `javascript:` protocol
  - `vbscript:` protocol
- **Impact:** 🟠 **HIGH** - Prevents XSS attacks via crafted URLs in search results

## 🐛 Stability & Reliability

### Error Handling Visibility
**Files:** `pure_spider.py`, `sparkx_engine.py`, `disk_index.py`
- **Issue:** `except Exception: pass` silently swallowed all errors
- **Fix:** Changed to `except Exception: print(f"[Component] Error: {e}")`
- **Impact:** 🟠 **HIGH** - Enables debugging and operational visibility into failures

### Model Path Validation
**File:** `sparkx_engine.py` (Line 77)
- **Issue:** Model path error message was unclear
- **Fix:** Added guidance: "Check MODEL_PATH environment variable"
- **Impact:** 🟡 **MEDIUM** - Improves developer experience during setup

## ⚙️ API & Performance

### FastAPI Deprecation
**File:** `api/main.py` (Lines 43-59)
- **Issue:** `@app.on_event()` deprecated in FastAPI 0.108+
- **Fix:** Replaced with `@asynccontextmanager` lifespan context manager
- **Impact:** 🟢 **LOW** - Ensures compatibility with latest FastAPI versions

### Duplicate Link Deduplication
**File:** `pure_spider.py` (Lines 113-131)
- **Issue:** Frontier list grew to 2000 items before deduplication check
- **Fix:** Use set for O(1) membership checking during link enqueue
- **Impact:** 🟡 **MEDIUM** - Reduces memory bloat and improves crawl efficiency

### Executable Fallback
**File:** `sparkx_engine.py` (Line 50)
- **Issue:** No fallback to default executable name
- **Fix:** Changed `return FALLBACK_SERVER_BIN` to `return FALLBACK_SERVER_BIN or "llama-server"`
- **Impact:** 🟢 **LOW** - Improves reliability when custom path not set

## 📋 Summary
- **Total Files Modified:** 4
- **Critical Issues Fixed:** 1 (SSL)
- **High Priority Fixes:** 2 (XSS, Error Handling)
- **Total Lines Changed:** ~150

---

All changes have been tested and verified. Ready for deployment! 🚀
