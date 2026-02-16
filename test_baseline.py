"""Step 5: Test baseline single-model analysis on tests/test_small/."""

import time
from src.baseline import run_baseline

TEST_PATH = "tests/test_small"

print("=" * 60)
print(f"Baseline Test: {TEST_PATH}")
print("=" * 60)

t0 = time.time()
result = run_baseline(
    codebase_path=TEST_PATH,
    verbose=True,
)
elapsed = time.time() - t0

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"\nTotal time:      {elapsed:.1f}s")
print(f"Analysis chars:  {len(result['analysis']):,}")
print(f"Prompt chars:    {result['prompt_chars']:,}")
print(f"Included files:  {result['included_files']}")
print(f"Excluded files:  {result['excluded_files']}")
print(f"\n{result['usage'].summary()}")

# ── Verify analysis is substantive ──
analysis = result["analysis"]
print(f"\n--- Analysis Preview (first 2000 chars) ---")
print(analysis[:2000])
if len(analysis) > 2000:
    print(f"... ({len(analysis) - 2000} more chars)")

# ── Check for planted bugs ──
print("\n--- Bug Detection Check ---")
analysis_lower = analysis.lower()

checks = [
    ("SQL injection", any(x in analysis_lower for x in ["sql injection", "sql-injection", "f-string", "f\"select", "string format"])),
    ("Hardcoded secret key", any(x in analysis_lower for x in ["secret_key", "hardcoded", "hard-coded", "secret key"])),
    ("Debug mode", any(x in analysis_lower for x in ["debug=true", "debug mode", "debug"])),
    ("MD5 hashing", any(x in analysis_lower for x in ["md5", "hash", "weak hash", "insecure hash"])),
    ("Unclosed DB connections", any(x in analysis_lower for x in ["connection", "close", "unclosed", "not closed", "resource leak"])),
]

found = 0
for name, detected in checks:
    status = "FOUND" if detected else "MISSED"
    print(f"  {status}: {name}")
    if detected:
        found += 1

print(f"\nDetected {found}/{len(checks)} planted bugs")

print("\n" + "=" * 60)
if len(analysis) > 500:
    print("Baseline test PASSED!")
else:
    print("Baseline test FAILED — analysis too short")
print("=" * 60)
