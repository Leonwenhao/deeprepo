"""Unit tests for RLMEngine._extract_code() — the code-block parser."""

import pytest
from unittest.mock import MagicMock

from deeprepo.rlm_scaffold import RLMEngine
from deeprepo.llm_clients import TokenUsage


@pytest.fixture
def engine():
    """Create an RLMEngine with mock clients (no real API keys needed)."""
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    return RLMEngine(root_client=root, sub_client=sub, usage=usage, verbose=False)


# ── 1. Basic extraction ────────────────────────────────────────────

def test_basic_python_block(engine):
    response = (
        "Here is the code:\n"
        "```python\n"
        "x = 1\n"
        "print(x)\n"
        "```\n"
        "That's it."
    )
    blocks = engine._extract_code(response)
    assert len(blocks) == 1
    assert "x = 1" in blocks[0]
    assert "print(x)" in blocks[0]


# ── 2. Nested backticks inside f-string (the core Bug 1 scenario) ──

def test_nested_backticks_in_fstring(engine):
    """Code block containing ``` inside an f-string for sub-LLM prompts.

    The old regex would truncate at the inner ``` — this test verifies
    the full code block is extracted including the llm_batch() call.
    """
    response = '''Here is the analysis code:
```python
prompts = {}
for name, content in codebase.items():
    prompts[name] = f"""Analyze this file:
```
{content}
```
Return JSON with keys: purpose, classes, functions."""

results = llm_batch(prompts)
for name, analysis in results.items():
    print(f"== {name} ==")
    print(analysis)
answer["ready"] = True
```
That completes the analysis.'''

    blocks = engine._extract_code(response)
    assert len(blocks) == 1
    # The critical check: llm_batch() must be present (not truncated)
    assert "llm_batch(prompts)" in blocks[0]
    assert 'answer["ready"] = True' in blocks[0]
    # The inner fences should be kept as part of the code
    assert "```" in blocks[0]


# ── 3. Prose-then-code ─────────────────────────────────────────────

def test_prose_before_code_not_extracted(engine):
    """A response that mixes prose with a fenced code block.

    Only the fenced block should be returned, not the prose.
    """
    response = (
        "Let me analyze this codebase step by step.\n"
        "First, I'll look at the file structure.\n"
        "\n"
        "```python\n"
        "for f in codebase:\n"
        '    print(f)\n'
        "```\n"
    )
    blocks = engine._extract_code(response)
    assert len(blocks) == 1
    assert "for f in codebase" in blocks[0]
    # Prose should NOT appear in any block
    for block in blocks:
        assert "Let me analyze" not in block


# ── 4. Multiple code blocks ────────────────────────────────────────

def test_multiple_code_blocks(engine):
    response = (
        "Step 1:\n"
        "```python\n"
        "x = 1\n"
        "```\n"
        "\n"
        "Step 2:\n"
        "```python\n"
        "y = 2\n"
        "```\n"
    )
    blocks = engine._extract_code(response)
    assert len(blocks) == 2
    assert "x = 1" in blocks[0]
    assert "y = 2" in blocks[1]


# ── 5. Fallback rejection — prose-only response ───────────────────

def test_fallback_rejects_pure_prose(engine):
    """A response with no fences and only English prose.

    The fallback heuristic should NOT return this as executable code.
    """
    response = (
        "Let me explain the architecture.\n"
        "The codebase uses a modular design.\n"
        "It has several entry points including main.py.\n"
        "Here is how the data flows through the system.\n"
    )
    blocks = engine._extract_code(response)
    assert blocks == []


# ── 6. Fallback accepts real unfenced code ─────────────────────────

def test_fallback_accepts_unfenced_code(engine):
    """When the model produces code without fences, fallback should catch it."""
    response = (
        "import json\n"
        "for f in codebase:\n"
        '    print(f)\n'
    )
    blocks = engine._extract_code(response)
    assert len(blocks) == 1
    assert "import json" in blocks[0]


# ── 7. _is_prose_line helper ───────────────────────────────────────

def test_is_prose_line():
    assert RLMEngine._is_prose_line("Let me analyze this.") is True
    assert RLMEngine._is_prose_line("Here is the code:") is True
    assert RLMEngine._is_prose_line("The function returns True.") is True
    assert RLMEngine._is_prose_line("* bullet point") is True
    assert RLMEngine._is_prose_line("1. numbered list") is True
    assert RLMEngine._is_prose_line("import os") is False
    assert RLMEngine._is_prose_line("x = 1") is False
    assert RLMEngine._is_prose_line("    indented_code()") is False
    assert RLMEngine._is_prose_line("") is False


# ── 8. Wrapped block: prose + inner fences in one outer fence ──────

def test_wrapped_block_prose_with_inner_fences(engine):
    """Model wraps prose + nested ```python blocks in one outer fence.

    The post-processor should split on inner fences and discard prose.
    """
    response = (
        "```python\n"
        "Let me analyze the v1 compatibility layer:\n"
        "\n"
        "```python\n"
        "v1_files = [f for f in codebase.keys()]\n"
        "print(v1_files)\n"
        "```\n"
        "\n"
        "Now let me check deprecated modules:\n"
        "\n"
        "```python\n"
        "dep = [f for f in codebase.keys() if 'deprecated' in f]\n"
        "print(dep)\n"
        "```\n"
        "```\n"
    )
    blocks = engine._extract_code(response)
    # Should extract the 2 inner code sections, not one blob with prose
    assert len(blocks) == 2
    assert "v1_files" in blocks[0]
    assert "dep" in blocks[1]
    # Prose should not be in any block
    for block in blocks:
        assert "Let me analyze" not in block
        assert "Now let me check" not in block


# ── 9. Code block starting with code is NOT split ─────────────────

def test_code_block_with_inner_fences_not_split(engine):
    """A code block that starts with actual code and contains ``` inside
    an f-string should NOT be split — it's a legitimate code pattern."""
    response = '''Here is the code:
```python
prompts = {}
for name, content in codebase.items():
    prompts[name] = f"""Analyze this file:
```
{content}
```
Return JSON."""

results = llm_batch(prompts)
```
Done.'''

    blocks = engine._extract_code(response)
    assert len(blocks) == 1
    assert "llm_batch(prompts)" in blocks[0]
