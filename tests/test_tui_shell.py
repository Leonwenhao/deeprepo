"""Tests for TUI shell module."""

from deeprepo.tui.shell import DeepRepoShell


def test_shell_creation():
    """DeepRepoShell can be instantiated."""
    shell = DeepRepoShell(".")
    assert shell.project_path
    assert shell.session is not None
    assert shell.prompt_builder is not None


def test_shell_creation_with_path(tmp_path):
    """DeepRepoShell resolves project path."""
    shell = DeepRepoShell(str(tmp_path))
    assert shell.project_path == str(tmp_path)


def test_handle_input_routes_slash_command(capsys):
    """Slash commands are routed through router and displayed."""
    shell = DeepRepoShell(".")
    shell.router.route = lambda text: {"status": "success", "message": f"ran {text}", "data": {}}
    shell._handle_slash_command("/status")
    captured = capsys.readouterr()
    assert "ran /status" in captured.out


def test_handle_input_routes_natural_language(capsys):
    """Non-slash input runs PromptBuilder and records prompt history."""
    shell = DeepRepoShell(".")
    shell.prompt_builder.build = lambda text: {
        "status": "success",
        "message": "built prompt",
        "data": {"prompt": f"PROMPT: {text}"},
    }

    history_before = len(shell.state.prompt_history)
    shell._handle_natural_language("fix the bug")
    captured = capsys.readouterr()
    assert "built prompt" in captured.out
    assert len(shell.state.prompt_history) == history_before + 1
    assert shell.state.prompt_history[-1]["user_input"] == "fix the bug"


def test_handle_input_dispatches_correctly():
    """_handle_input routes to the right handler."""
    shell = DeepRepoShell(".")
    calls = []
    shell._handle_slash_command = lambda text: calls.append(("slash", text))
    shell._handle_natural_language = lambda text: calls.append(("nl", text))

    shell._handle_input("/init")
    shell._handle_input("fix the WebSocket bug")

    assert calls == [("slash", "/init"), ("nl", "fix the WebSocket bug")]


def test_print_welcome_does_not_crash(capsys):
    """Welcome banner prints without error."""
    shell = DeepRepoShell(".")
    shell._print_welcome()
    captured = capsys.readouterr()
    assert "deeprepo" in captured.out


def test_print_goodbye_does_not_crash(capsys):
    """Goodbye message prints without error."""
    shell = DeepRepoShell(".")
    shell._print_goodbye()
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_display_result_formats_statuses(capsys):
    """_display_result emits status-specific content."""
    shell = DeepRepoShell(".")
    shell._display_result({"status": "success", "message": "done", "data": {}})
    shell._display_result({"status": "error", "message": "bad", "data": {}})
    shell._display_result({"status": "info", "message": "note", "data": {}})

    captured = capsys.readouterr()
    assert "done" in captured.out
    assert "bad" in captured.out
    assert "note" in captured.out


def test_display_result_prints_help_text(capsys):
    """_display_result prints help text when provided."""
    shell = DeepRepoShell(".")
    shell._display_result(
        {
            "status": "success",
            "message": "Available commands",
            "data": {"help_text": "/help\n/status"},
        }
    )

    captured = capsys.readouterr()
    assert "Available commands" in captured.out
    assert "/help" in captured.out
