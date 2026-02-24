"""Tests for REPL code execution safety in RLMEngine."""

import signal
import sys
from unittest.mock import MagicMock

import pytest

from deeprepo.llm_clients import TokenUsage
from deeprepo.rlm_scaffold import RLMEngine


@pytest.fixture
def engine():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    return RLMEngine(root_client=root, sub_client=sub, usage=usage, verbose=False)


@pytest.fixture
def restricted_namespace(engine):
    return engine._build_namespace(
        documents={},
        file_tree="",
        metadata={},
        answer={"content": "", "ready": False},
    )


def test_sys_exit_caught_not_fatal(engine):
    """H2: sys.exit() in REPL code should be caught, not kill the process."""
    namespace = {"sys": sys, "__builtins__": {}}
    output = engine._execute_code("sys.exit(0)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output


def test_sys_exit_nonzero_caught(engine):
    """H2: sys.exit(1) should also be caught."""
    namespace = {"sys": sys, "__builtins__": {}}
    output = engine._execute_code("sys.exit(1)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="signal.SIGALRM not available")
def test_execution_timeout(engine):
    """H3: Long-running code should be interrupted by timeout."""
    import deeprepo.rlm_scaffold as scaffold

    original_timeout = scaffold.EXEC_TIMEOUT_SECONDS
    scaffold.EXEC_TIMEOUT_SECONDS = 2

    try:
        namespace = {"__builtins__": {}}
        output = engine._execute_code("while True:\n    pass", namespace)

        assert "EXECUTION ERROR" in output
        assert "timed out" in output.lower()
    finally:
        scaffold.EXEC_TIMEOUT_SECONDS = original_timeout


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("open('pyproject.toml').read()", "NameError"),
        ("__import__('os')", "NameError"),
        ("eval('1+1')", "NameError"),
        ("os.system('echo not_allowed')", "AttributeError"),
    ],
)
def test_restricted_namespace_blocks_dangerous_calls(
    engine,
    restricted_namespace,
    code,
    expected,
):
    output = engine._execute_code(code, restricted_namespace)

    assert "EXECUTION ERROR" in output
    assert expected in output


@pytest.mark.parametrize(
    "code",
    [
        "import os\nprint('x')",
        "from os import path\nprint(path.basename('a/b'))",
    ],
)
def test_import_statements_blocked_by_ast_precheck(engine, restricted_namespace, code):
    output = engine._execute_code(code, restricted_namespace)

    assert "EXECUTION ERROR" in output
    assert "PermissionError" in output
    assert "Import statements are blocked" in output


def test_allowlisted_builtins_still_work(engine, restricted_namespace):
    output = engine._execute_code(
        "nums = [3, 1, 2]\nprint(sum(sorted(nums)))",
        restricted_namespace,
    )

    assert output.strip() == "6"
