"""Step 3: Verify prompts are valid and template formats correctly."""

from deeprepo.prompts import ROOT_SYSTEM_PROMPT, SUB_SYSTEM_PROMPT, ROOT_USER_PROMPT_TEMPLATE

print("=" * 60)
print("TEST: Prompts Verification")
print("=" * 60)

# ── Verify they're non-empty strings ──
assert isinstance(ROOT_SYSTEM_PROMPT, str) and len(ROOT_SYSTEM_PROMPT) > 100
print(f"ROOT_SYSTEM_PROMPT: {len(ROOT_SYSTEM_PROMPT)} chars — OK")

assert isinstance(SUB_SYSTEM_PROMPT, str) and len(SUB_SYSTEM_PROMPT) > 50
print(f"SUB_SYSTEM_PROMPT:  {len(SUB_SYSTEM_PROMPT)} chars — OK")

assert isinstance(ROOT_USER_PROMPT_TEMPLATE, str) and len(ROOT_USER_PROMPT_TEMPLATE) > 50
print(f"ROOT_USER_PROMPT_TEMPLATE: {len(ROOT_USER_PROMPT_TEMPLATE)} chars — OK")

# ── Verify template has expected placeholders ──
assert "{metadata_str}" in ROOT_USER_PROMPT_TEMPLATE, "Missing {metadata_str} placeholder"
assert "{file_tree}" in ROOT_USER_PROMPT_TEMPLATE, "Missing {file_tree} placeholder"
print("  Template placeholders present — OK")

# ── Verify template formats without error ──
formatted = ROOT_USER_PROMPT_TEMPLATE.format(
    metadata_str="Repository: test_repo\nTotal files: 3",
    file_tree="test_repo/\n  app.py\n  utils.py",
)
assert "test_repo" in formatted
assert "app.py" in formatted
print(f"  Template formatted successfully ({len(formatted)} chars) — OK")

# ── Verify key content in root system prompt ──
assert "codebase" in ROOT_SYSTEM_PROMPT, "Should mention codebase variable"
assert "llm_query" in ROOT_SYSTEM_PROMPT, "Should mention llm_query function"
assert "llm_batch" in ROOT_SYSTEM_PROMPT, "Should mention llm_batch function"
assert "answer" in ROOT_SYSTEM_PROMPT, "Should mention answer variable"
assert "set_answer" in ROOT_SYSTEM_PROMPT, "Should mention set_answer function"
print("  Root prompt references all REPL variables/functions — OK")

# ── Verify key content in sub system prompt ──
assert "analysis" in SUB_SYSTEM_PROMPT.lower() or "analyze" in SUB_SYSTEM_PROMPT.lower()
assert "bug" in SUB_SYSTEM_PROMPT.lower() or "issue" in SUB_SYSTEM_PROMPT.lower()
print("  Sub prompt covers analysis tasks — OK")

print("\n" + "=" * 60)
print("All prompt tests PASSED!")
print("=" * 60)
