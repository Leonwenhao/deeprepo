"""Tests for TUI command router."""

import deeprepo.cli_commands as cli_commands
from deeprepo.tui.command_router import CommandRouter


def test_router_creation():
    """CommandRouter can be instantiated."""
    router = CommandRouter(".")
    assert router.project_path == "."
    assert "help" in router._commands


def test_route_help_returns_command_list():
    """`/help` returns a success result with commands and help text."""
    router = CommandRouter(".")
    result = router.route("/help")

    assert result["status"] == "success"
    assert "commands" in result["data"]
    assert "help_text" in result["data"]
    assert "status" in result["data"]["commands"]


def test_route_empty_returns_error():
    """`/` returns a structured error result."""
    router = CommandRouter(".")
    result = router.route("/")
    assert result["status"] == "error"
    assert "Empty command" in result["message"]


def test_route_unknown_command_returns_error():
    """Unknown slash command returns available command list."""
    router = CommandRouter(".")
    result = router.route("/nonexistent")
    assert result["status"] == "error"
    assert "Unknown command" in result["message"]
    assert "/help" in result["message"]


def test_route_parse_error_returns_error():
    """Invalid quoting returns parse error instead of crashing."""
    router = CommandRouter(".")
    result = router.route('/log add "unterminated')
    assert result["status"] == "error"
    assert "Parse error:" in result["message"]


def test_route_status_dispatches_to_cmd_status(monkeypatch, tmp_path):
    """`/status` calls cmd_status with path and quiet=True."""
    captured = {}

    def fake_cmd_status(args, *, quiet=False):
        captured["path"] = args.path
        captured["quiet"] = quiet
        return {"status": "success", "message": "status ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_status", fake_cmd_status)
    router = CommandRouter(str(tmp_path))
    result = router.route("/status")

    assert result["status"] == "success"
    assert captured["path"] == str(tmp_path)
    assert captured["quiet"] is True


def test_route_context_defaults_to_copy_markdown(monkeypatch, tmp_path):
    """`/context` defaults to copy=True and format=markdown in TUI."""
    captured = {}

    def fake_cmd_context(args, *, quiet=False):
        captured["path"] = args.path
        captured["copy"] = args.copy
        captured["format"] = args.format
        captured["quiet"] = quiet
        return {"status": "success", "message": "context ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_context", fake_cmd_context)
    router = CommandRouter(str(tmp_path))
    result = router.route("/context")

    assert result["status"] == "success"
    assert captured["path"] == str(tmp_path)
    assert captured["copy"] is True
    assert captured["format"] == "markdown"
    assert captured["quiet"] is True


def test_route_context_passes_format_and_no_copy(monkeypatch, tmp_path):
    """`/context --format cursor --no-copy` is parsed correctly."""
    captured = {}

    def fake_cmd_context(args, *, quiet=False):
        captured["copy"] = args.copy
        captured["format"] = args.format
        captured["quiet"] = quiet
        return {"status": "success", "message": "context ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_context", fake_cmd_context)
    router = CommandRouter(str(tmp_path))
    result = router.route("/context --format cursor --no-copy")

    assert result["status"] == "success"
    assert captured["copy"] is False
    assert captured["format"] == "cursor"
    assert captured["quiet"] is True


def test_route_log_defaults_to_show_mode(monkeypatch, tmp_path):
    """`/log` defaults to show mode with count=5."""
    captured = {}

    def fake_cmd_log(args, *, quiet=False):
        captured["path"] = args.path
        captured["action"] = args.action
        captured["count"] = args.count
        captured["quiet"] = quiet
        return {"status": "success", "message": "log ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_log", fake_cmd_log)
    router = CommandRouter(str(tmp_path))
    result = router.route("/log")

    assert result["status"] == "success"
    assert captured["path"] == str(tmp_path)
    assert captured["action"] == "show"
    assert captured["count"] == 5
    assert captured["quiet"] is True


def test_route_log_add_joins_message(monkeypatch, tmp_path):
    """`/log add ...` joins remaining tokens into the log message."""
    captured = {}

    def fake_cmd_log(args, *, quiet=False):
        captured["action"] = args.action
        captured["quiet"] = quiet
        return {"status": "success", "message": "log ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_log", fake_cmd_log)
    router = CommandRouter(str(tmp_path))
    result = router.route("/log add Fixed the WebSocket bug")

    assert result["status"] == "success"
    assert captured["action"] == "Fixed the WebSocket bug"
    assert captured["quiet"] is True


def test_route_refresh_passes_full_flag(monkeypatch, tmp_path):
    """`/refresh --full` passes full=True and quiet=True."""
    captured = {}

    def fake_cmd_refresh(args, *, quiet=None):
        captured["path"] = args.path
        captured["full"] = args.full
        captured["quiet_arg"] = args.quiet
        captured["quiet_kw"] = quiet
        return {"status": "success", "message": "refresh ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_refresh", fake_cmd_refresh)
    router = CommandRouter(str(tmp_path))
    result = router.route("/refresh --full")

    assert result["status"] == "success"
    assert captured["path"] == str(tmp_path)
    assert captured["full"] is True
    assert captured["quiet_arg"] is True
    assert captured["quiet_kw"] is True


def test_route_handler_exception_returns_error():
    """Exceptions inside handlers are returned as command errors."""
    router = CommandRouter(".")

    def _boom(tokens):
        raise RuntimeError("boom")

    router._commands["help"]["handler"] = _boom
    result = router.route("/help")

    assert result["status"] == "error"
    assert "Command failed: boom" in result["message"]


def test_route_quit_returns_exit_status():
    """`/quit` returns exit status for shell loop termination."""
    router = CommandRouter(".")
    result = router.route("/quit")
    assert result["status"] == "exit"
    assert result["message"] == "Goodbye."


def test_route_exit_returns_exit_status():
    """`/exit` returns exit status for shell loop termination."""
    router = CommandRouter(".")
    result = router.route("/exit")
    assert result["status"] == "exit"
    assert result["message"] == "Goodbye."


def test_route_init_auto_forces_when_project_md_missing(tmp_path, monkeypatch):
    """Auto-force `/init` when .deeprepo exists but PROJECT.md is missing."""
    captured = {}

    def fake_cmd_init(args, *, quiet=False):
        captured["path"] = args.path
        captured["force"] = args.force
        captured["quiet_arg"] = args.quiet
        captured["quiet_kw"] = quiet
        return {"status": "success", "message": "init ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_init", fake_cmd_init)

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)

    router = CommandRouter(str(tmp_path))
    result = router.route("/init")

    assert result["status"] == "success"
    assert captured["path"] == str(tmp_path)
    assert captured["force"] is True
    assert captured["quiet_arg"] is True
    assert captured["quiet_kw"] is True


def test_route_init_requires_force_when_project_md_exists(tmp_path, monkeypatch):
    """Do not auto-force `/init` when PROJECT.md exists unless --force is passed."""
    captured = {}

    def fake_cmd_init(args, *, quiet=False):
        captured["force"] = args.force
        return {"status": "success", "message": "init ok", "data": {}}

    monkeypatch.setattr(cli_commands, "cmd_init", fake_cmd_init)

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")

    router = CommandRouter(str(tmp_path))
    result = router.route("/init")

    assert result["status"] == "success"
    assert captured["force"] is False


def test_route_init_rewrites_env_error(monkeypatch, tmp_path):
    """M2: /init with missing ANTHROPIC_API_KEY shows user-friendly error."""
    def fake_cmd_init(args, *, quiet=False):
        del args, quiet
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file or export it."
        )

    monkeypatch.setattr(cli_commands, "cmd_init", fake_cmd_init)

    router = CommandRouter(str(tmp_path))
    result = router.route("/init")

    assert result["status"] == "error"
    assert "export ANTHROPIC_API_KEY" in result["message"]
    assert ".env" not in result["message"]
