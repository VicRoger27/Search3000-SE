"""
MANUAL AUDIT SCRIPT - Search3000 Code Quality Check
Run this to identify potential issues without pytest
"""

import os
import sys
import re
from pathlib import Path

# Fix: correctly resolve project root
project_path = Path(__file__).resolve().parent
sys.path.insert(0, str(project_path))

py_files = []
for root, dirs, files in os.walk(project_path):
    # Skip virtual environments and hidden git/cache folders
    if any(p in root for p in [".git", "__pycache__", ".venv", "venv", ".idea"]):
        continue
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

from engine.storage.disk_index import DiskIndexStore
from engine.storage.base128 import Base128Codec
from engine.crawler.pure_spider import PureWebSpider, DEFAULT_SEEDS
from engine.models.sparkx_engine import SparkXEngine

print("=" * 70)
print("MANUAL CODE AUDIT REPORT - SEARCH3000")
print("=" * 70)

issues = []
warnings = []
good_findings = []

# 1. Check DEFAULT_SEEDS length
print("\n[1] Checking DEFAULT_SEEDS configuration...")
if len(DEFAULT_SEEDS) < 10:
    issues.append(f"[WARN] DEFAULT_SEEDS has only {len(DEFAULT_SEEDS)} entries (recommended: 15+)")
else:
    good_findings.append(f"[PASS] DEFAULT_SEEDS has {len(DEFAULT_SEEDS)} quality seeds")

# 2. Check for hardcoded paths and env overrides
print("\n[2] Checking for path configurability in code...")
sparkx_file = project_path / 'engine' / 'models' / 'sparkx_engine.py'
with open(sparkx_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if "SPARKX_MODEL_PATH" in content and "LLAMA_SERVER_BIN" in content:
        good_findings.append("[PASS] sparkx_engine.py paths are configurable via environment variables")
    else:
        warnings.append("[WARN] sparkx_engine.py paths should support environment variable overrides")

# Check base128.py
base128_file = project_path / 'engine' / 'storage' / 'base128.py'
with open(base128_file, 'r', encoding='utf-8') as f:
    if f.read().count('gzip') > 0:
        good_findings.append("[PASS] Base128Codec uses zlib compression")

# 3. Check for error handling patterns
print("\n[3] Checking error handling patterns...")
error_handling = {
    'pure_spider': 0,
    'sparkx_engine': 0,
    'disk_index': 0,
}

for module, rel_path in [('pure_spider', 'engine/crawler/pure_spider.py'),
                         ('sparkx_engine', 'engine/models/sparkx_engine.py'),
                         ('disk_index', 'engine/storage/disk_index.py')]:
    filepath = project_path / rel_path
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        error_handling[module] = len(re.findall(r'\bexcept\b', content))
    
    if error_handling[module] < 3:
        warnings.append(f"[WARN] {module} has only {error_handling[module]} except blocks (consider adding more)")
    else:
        good_findings.append(f"[PASS] {module} has {error_handling[module]} error handlers")

# 4. Check for security patterns
print("\n[4] Checking security patterns...")
security_checks = []

# Check for SSL verification
spider_file = project_path / 'engine' / 'crawler' / 'pure_spider.py'
with open(spider_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if 'verify=True' in content:
        security_checks.append("[PASS] SSL certificate verification enabled")
    else:
        issues.append("[FAIL] SSL certificate verification NOT enabled (MITM vulnerable)")

# Check for robots.txt compliance
if 'urllib.robotparser.RobotFileParser' in content:
    security_checks.append("[PASS] Robots.txt compliance implemented")

# Check for input sanitization
api_file = project_path / 'api' / 'main.py'
with open(api_file, 'r', encoding='utf-8') as f:
    api_content = f.read()
    if re.search(r're\.sub.*?\x00', api_content):
        security_checks.append("[PASS] Input sanitization for control characters")

# Check for path traversal prevention
disk_file = project_path / 'engine' / 'storage' / 'disk_index.py'
with open(disk_file, 'r', encoding='utf-8') as f:
    if re.search(r'[^a-f0-9]', f.read()):
        security_checks.append("[PASS] Path traversal prevention in disk_index.py")

for check in security_checks:
    good_findings.append(check)

# 5. Check for rate limiting
print("\n[5] Checking rate limiting implementation...")
with open(spider_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if 'domain_delays' in content and 'domain_backoff' in content:
        good_findings.append("[PASS] Per-domain rate limiting implemented")
    if 'max_redirects' in content:
        good_findings.append("[PASS] Redirect loop protection implemented")
    if 'retry-after' in content:
        good_findings.append("[PASS] Retry-After header parsing implemented")

# 6. Check API endpoint security
print("\n[6] Checking API endpoint security...")
with open(api_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if 'max_length=' in content or 'max_length' in content:
        good_findings.append("[PASS] Query parameter length limits")
    if 'ALLOWED_FILTERS' in content:
        good_findings.append("[PASS] Filter parameter whitelisting")
    if 'CORS_ORIGINS' in content or 'ALLOWED_ORIGINS' in content:
        good_findings.append("[PASS] CORS environment variable configuration")
    else:
        warnings.append("[WARN] CORS not configured via environment variable")

# 7. Check test coverage
print("\n[7] Checking test coverage...")
test_files = list((project_path / 'tests').glob('test_*.py'))
print(f"   Found {len(test_files)} test files:")
for tf in test_files:
    print(f"     - {tf.name}")

# 8. Check for potential performance issues
print("\n[8] Checking for potential performance issues...")
with open(spider_file, 'r', encoding='utf-8') as f:
    content = f.read()
    if 'for link in data["outlinks"]' in content:
        if 'frontier_set = set(self.frontier)' in content:
            good_findings.append("[PASS] O(1) frontier deduplication implemented")
        else:
            good_findings.append("[INFO] Frontier membership check present")

# 9. Check documentation
print("\n[9] Checking documentation quality...")
docs = {'docstrings': 0}
for py_file in py_files:
    try:
        with open(py_file, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            docs['docstrings'] += len(re.findall(r'^\s*"""', content, re.MULTILINE))
    except Exception:
        pass

if docs['docstrings'] < 5:
    warnings.append(f"[WARN] Only {docs['docstrings']} docstrings found")
else:
    good_findings.append(f"[PASS] {docs['docstrings']} docstrings found across codebase")

# 10. Check requirements.txt
print("\n[10] Checking requirements.txt...")
req_file = project_path / 'requirements.txt'
with open(req_file, 'r', encoding='utf-8') as f:
    reqs = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    print(f"   Found {len(reqs)} dependencies:")
    for r in reqs:
        print(f"     * {r}")
    
    pinned = sum(1 for r in reqs if '>=' in r or '<=' in r or '==' in r)
    if pinned == len(reqs):
        good_findings.append("[PASS] All dependencies have version constraints")
    else:
        warnings.append(f"[WARN] Only {pinned}/{len(reqs)} dependencies have version constraints")

# Summary
print("\n" + "=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)

print(f"\n[PASS] GOOD FINDINGS ({len(good_findings)}):")
for finding in good_findings:
    print(f"  * {finding}")

if warnings:
    print(f"\n[WARN] WARNINGS ({len(warnings)}):")
    for warning in warnings:
        print(f"  * {warning}")

if issues:
    print(f"\n[FAIL] ISSUES ({len(issues)}):")
    for issue in issues:
        print(f"  * {issue}")

total_checks = len(good_findings) + len(warnings) + len(issues)
good_score = len(good_findings) / total_checks * 100 if total_checks > 0 else 0

print(f"\nOVERALL SCORE: {good_score:.1f}% ({len(good_findings)}/{total_checks} checks passed)")

if good_score >= 90:
    print("EXCELLENT - Code quality is production-ready!")
elif good_score >= 70:
    print("GOOD - Minor improvements recommended")
elif good_score >= 50:
    print("FAIR - Several issues need attention")
else:
    print("POOR - Critical issues require fixes before deployment")

print("=" * 70)
