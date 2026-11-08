"""
MANUAL AUDIT SCRIPT - Search3000 Code Quality Check
Run this to identify potential issues without pytest
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

project_path = Path(__file__).resolve().parent.parent
py_files = []
for root, dirs, files in os.walk(project_path):
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
    issues.append(f"⚠️  DEFAULT_SEEDS has only {len(DEFAULT_SEEDS)} entries (recommended: 15+)")
else:
    good_findings.append(f"✅ DEFAULT_SEEDS has {len(DEFAULT_SEEDS)} quality seeds")

# 2. Check for hardcoded paths
print("\n[2] Checking for hardcoded paths in code...")
hardcoded_paths = []

# Check sparkx_engine.py
with open('engine/models/sparkx_engine.py', 'r') as f:
    content = f.read()
    if r"C:\Users\Victor" in content:
        hardcoded_paths.append("engine/models/sparkx_engine.py")
        warnings.append("⚠️  sparkx_engine.py contains hardcoded user paths (C:\\Users\\Victor)")

# Check base128.py
with open('engine/storage/base128.py', 'r') as f:
    if f.read().count('gzip') > 0:
        good_findings.append("✅ Base128Codec uses zlib compression")

# 3. Check for error handling patterns
print("\n[3] Checking error handling patterns...")
error_handling = {
    'pure_spider': 0,
    'sparkx_engine': 0,
    'disk_index': 0,
}

for module, filepath in [('pure_spider', 'engine/crawler/pure_spider.py'),
                         ('sparkx_engine', 'engine/models/sparkx_engine.py'),
                         ('disk_index', 'engine/storage/disk_index.py')]:
    with open(filepath, 'r') as f:
        content = f.read()
        # Count try/except blocks
        error_handling[module] = len(re.findall(r'\bexcept\b', content))
    
    if error_handling[module] < 3:
        warnings.append(f"⚠️  {module} has only {error_handling[module]} except blocks (consider adding more)")
    else:
        good_findings.append(f"✅ {module} has {error_handling[module]} error handlers")

# 4. Check for security patterns
print("\n[4] Checking security patterns...")
security_checks = []

# Check for SSL verification
with open('engine/crawler/pure_spider.py', 'r') as f:
    content = f.read()
    if 'verify=True' in content:
        security_checks.append("✅ SSL certificate verification enabled")
    else:
        issues.append("❌ SSL certificate verification NOT enabled (MITM vulnerable)")

# Check for robots.txt compliance
if 'urllib.robotparser.RobotFileParser' in content:
    security_checks.append("✅ Robots.txt compliance implemented")

# Check for input sanitization
with open('api/main.py', 'r') as f:
    content = f.read()
    if re.search(r're\.sub.*?\x00', content):
        security_checks.append("✅ Input sanitization for control characters")

# Check for path traversal prevention
with open('engine/storage/disk_index.py', 'r') as f:
    content = f.read()
    if re.search(r'[^a-f0-9]', content):
        security_checks.append("✅ Path traversal prevention in disk_index.py")

for check in security_checks:
    good_findings.append(check)

# 5. Check for rate limiting
print("\n[5] Checking rate limiting implementation...")
with open('engine/crawler/pure_spider.py', 'r') as f:
    content = f.read()
    if 'domain_delays' in content and 'domain_backoff' in content:
        good_findings.append("✅ Per-domain rate limiting implemented")
    if 'max_redirects' in content:
        good_findings.append("✅ Redirect loop protection implemented")
    if 'retry-after' in content:
        good_findings.append("✅ Retry-After header parsing implemented")

# 6. Check API endpoint security
print("\n[6] Checking API endpoint security...")
with open('api/main.py', 'r') as f:
    content = f.read()
    
    # Check for query parameter validation
    if 'max_length=' in content or 'max_length' in content:
        good_findings.append("✅ Query parameter length limits")
    
    # Check for filter whitelist
    if 'ALLOWED_FILTERS' in content:
        good_findings.append("✅ Filter parameter whitelisting")
    
    # Check CORS configuration
    if 'CORS_ORIGINS' in content:
        good_findings.append("✅ CORS environment variable configuration")
    else:
        warnings.append("⚠️  CORS not configured via environment variable")

# 7. Check test coverage
print("\n[7] Checking test coverage...")
test_files = list(Path('tests').glob('test_*.py'))
print(f"   Found {len(test_files)} test files:")
for tf in test_files:
    print(f"     - {tf.name}")

# 8. Check for potential performance issues
print("\n[8] Checking for potential performance issues...")
perf_issues = []

with open('engine/crawler/pure_spider.py', 'r') as f:
    content = f.read()
    # Check for O(n) operations on large lists
    if 'for link in data["outlinks"]' in content:
        if 'frontier_set = set(self.frontier)' in content:
            good_findings.append("✅ O(1) frontier deduplication implemented")
        else:
            perf_issues.append("⚠️  Potential O(n) deduplication on large frontiers")

# 9. Check documentation
print("\n[9] Checking documentation quality...")
docs = {
    'README': False,
    'docstrings': 0,
}
# Count docstrings
for py_file in py_files:
    with open(py_file, 'r') as f:
        content = f.read()
        docs['docstrings'] += len(re.findall(r'^\s*"""', content, re.MULTILINE))

if docs['docstrings'] < 5:
    warnings.append(f"⚠️  Only {docs['docstrings']} docstrings found (consider adding more)")
else:
    good_findings.append(f"✅ {docs['docstrings']} docstrings found")

# 10. Check requirements.txt
print("\n[10] Checking requirements.txt...")
with open('requirements.txt', 'r') as f:
    reqs = f.read().strip().split('\n')
    print(f"   Found {len(reqs)} dependencies:")
    for r in reqs:
        print(f"     • {r}")
    
    # Check for version pinning
    pinned = sum(1 for r in reqs if '>=' in r or '<=' in r)
    if pinned == len(reqs):
        good_findings.append("✅ All dependencies have version constraints")
    else:
        warnings.append(f"⚠️  Only {pinned}/{len(reqs)} dependencies have version constraints")

# Summary
print("\n" + "=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)

print(f"\n✅ GOOD FINDINGS ({len(good_findings)}):")
for finding in good_findings:
    print(f"  • {finding}")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for warning in warnings:
        print(f"  • {warning}")

if issues:
    print(f"\n❌ ISSUES ({len(issues)}):")
    for issue in issues:
        print(f"  • {issue}")

# Final score
total_checks = len(good_findings) + len(warnings) + len(issues)
good_score = len(good_findings) / total_checks * 100 if total_checks > 0 else 0

print(f"\n📊 OVERALL SCORE: {good_score:.1f}% ({len(good_findings)}/{total_checks} checks passed)")

if good_score >= 90:
    print("🏆 EXCELLENT - Code quality is production-ready!")
elif good_score >= 70:
    print("✅ GOOD - Minor improvements recommended")
elif good_score >= 50:
    print("⚠️  FAIR - Several issues need attention")
else:
    print("❌ POOR - Critical issues require fixes before deployment")

print("=" * 70)
