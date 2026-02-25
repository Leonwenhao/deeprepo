"""Tests for S8 CLI entry point wiring."""

import logging
import sys

import pytest


def test_version_is_0_2_5():
    """Package version was bumped to 0.2.5."""
    import deeprepo

    assert deeprepo.__version__ == "0.2.5"


def test_no_args_launches_tui(monkeypatch):
    """Running deeprepo with no args launches the TUI shell."""
    monkeypatch.setattr(sys, "argv", ["deeprepo"])

    launched = []

    class FakeShell:
        def __init__(self, path):
            self.path = path

        def run(self):
            launched.append(self.path)

    monkeypatch.setattr("deeprepo.tui.shell.DeepRepoShell", FakeShell)

    from deeprepo.cli import main

    main()

    assert len(launched) == 1
    assert launched[0] == "."


def test_tui_subcommand_launches_tui(monkeypatch):
    """Running 'deeprepo tui' launches the TUI shell."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "tui"])

    launched = []

    class FakeShell:
        def __init__(self, path):
            self.path = path

        def run(self):
            launched.append(self.path)

    monkeypatch.setattr("deeprepo.tui.shell.DeepRepoShell", FakeShell)

    from deeprepo.cli import main

    main()

    assert len(launched) == 1
    assert launched[0] == "."


def test_tui_subcommand_accepts_path(monkeypatch):
    """Running 'deeprepo tui /some/path' passes the path to TUI shell."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "tui", "/tmp/myproject"])

    launched = []

    class FakeShell:
        def __init__(self, path):
            self.path = path

        def run(self):
            launched.append(self.path)

    monkeypatch.setattr("deeprepo.tui.shell.DeepRepoShell", FakeShell)

    from deeprepo.cli import main

    main()

    assert len(launched) == 1
    assert launched[0] == "/tmp/myproject"


def test_no_tui_flag_prints_help(monkeypatch, capsys):
    """Running 'deeprepo --no-tui' prints help instead of launching TUI."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "--no-tui"])

    from deeprepo.cli import main

    try:
        main()
    except SystemExit as e:
        assert e.code == 1

    captured = capsys.readouterr()
    assert "deeprepo" in captured.out


def test_existing_commands_still_work(monkeypatch):
    """Running 'deeprepo status' still dispatches to cmd_status."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "status"])

    called = []
    monkeypatch.setattr(
        "deeprepo.cli_commands.cmd_status",
        lambda args, **kwargs: called.append("status") or {"status": "success", "message": "", "data": {}},
    )

    from deeprepo.cli import main

    main()

    assert "status" in called


def test_analyze_default_max_turns_is_20(monkeypatch):
    """`deeprepo analyze` should default to 20 max turns."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "analyze", "."])

    captured = {}

    def _fake_analyze(args):
        captured["max_turns"] = args.max_turns

    monkeypatch.setattr("deeprepo.cli.cmd_analyze", _fake_analyze)

    from deeprepo.cli import main

    main()

    assert captured["max_turns"] == 20


def test_compare_default_max_turns_is_20(monkeypatch):
    """`deeprepo compare` should default to 20 max turns."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "compare", "."])

    captured = {}

    def _fake_compare(args):
        captured["max_turns"] = args.max_turns

    monkeypatch.setattr("deeprepo.cli.cmd_compare", _fake_compare)

    from deeprepo.cli import main

    main()

    assert captured["max_turns"] == 20


def test_debug_flag_enables_logging_configuration(monkeypatch):
    """`--debug` should configure DEBUG logging."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "--debug", "--no-tui"])

    called = {}

    def _fake_basic_config(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("deeprepo.cli.logging.basicConfig", _fake_basic_config)

    from deeprepo.cli import main

    with pytest.raises(SystemExit):
        main()

    assert called["level"] == logging.DEBUG


def test_deeprepo_debug_env_enables_logging_configuration(monkeypatch):
    """DEEPREPO_DEBUG=1 should configure DEBUG logging without --debug."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "--no-tui"])
    monkeypatch.setenv("DEEPREPO_DEBUG", "1")

    called = {}

    def _fake_basic_config(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("deeprepo.cli.logging.basicConfig", _fake_basic_config)

    from deeprepo.cli import main

    with pytest.raises(SystemExit):
        main()

    assert called["level"] == logging.DEBUG


def test_logging_not_configured_without_debug_flag_or_env(monkeypatch):
    """Without --debug or env var, logging config should remain unchanged."""
    monkeypatch.setattr(sys, "argv", ["deeprepo", "--no-tui"])
    monkeypatch.delenv("DEEPREPO_DEBUG", raising=False)

    called = {"count": 0}

    def _fake_basic_config(**_kwargs):
        called["count"] += 1

    monkeypatch.setattr("deeprepo.cli.logging.basicConfig", _fake_basic_config)

    from deeprepo.cli import main

    with pytest.raises(SystemExit):
        main()

    assert called["count"] == 0
