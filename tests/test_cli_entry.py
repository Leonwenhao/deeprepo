"""Tests for S8 CLI entry point wiring."""

import sys


def test_version_is_0_2_1():
    """Package version was bumped to 0.2.1."""
    import deeprepo

    assert deeprepo.__version__ == "0.2.1"


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
