"""Tests for REPL code execution safety in RLMEngine."""

import signal
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


def test_sys_exit_caught_not_fatal(engine):
    """H2: sys.exit() in REPL code should be caught, not kill the process."""
    namespace = {"__builtins__": __builtins__}
    output = engine._execute_code("import sys; sys.exit(0)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output


def test_sys_exit_nonzero_caught(engine):
    """H2: sys.exit(1) should also be caught."""
    namespace = {"__builtins__": __builtins__}
    output = engine._execute_code("import sys; sys.exit(1)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="signal.SIGALRM not available")
def test_execution_timeout(engine):
    """H3: Long-running code should be interrupted by timeout."""
    import deeprepo.rlm_scaffold as scaffold

    original_timeout = scaffold.EXEC_TIMEOUT_SECONDS
    scaffold.EXEC_TIMEOUT_SECONDS = 2

    try:
        namespace = {"__builtins__": __builtins__}
        output = engine._execute_code("import time; time.sleep(999)", namespace)

        assert "EXECUTION ERROR" in output
        assert "timed out" in output.lower()
    finally:
        scaffold.EXEC_TIMEOUT_SECONDS = original_timeout
