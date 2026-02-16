"""Step 4: Integration test — run full RLM analysis on tests/test_small/."""

import time
from src.rlm_scaffold import run_analysis

TEST_PATH = "tests/test_small"

print("=" * 60)
print(f"RLM Integration Test: {TEST_PATH}")
print("=" * 60)

t0 = time.time()
result = run_analysis(
    codebase_path=TEST_PATH,
    verbose=True,
    max_turns=10,  # cap at 10 for test
)
elapsed = time.time() - t0

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"\nTurns taken:    {result['turns']}")
print(f"Total time:     {elapsed:.1f}s")
print(f"Analysis chars: {len(result['analysis']):,}")
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

# ── Verify cost is reasonable ──
cost = result["usage"].total_cost
print(f"\nTotal cost: ${cost:.4f}")
if cost < 0.50:
    print("  Cost under $0.50 — OK")
else:
    print(f"  WARNING: Cost exceeded $0.50 target")

print("\n" + "=" * 60)
if found >= 3 and len(analysis) > 500:
    print("Integration test PASSED!")
else:
    print(f"Integration test PARTIAL — detected {found}/5 bugs, analysis {len(analysis)} chars")
print("=" * 60)
