"""Tests for S7 TUI polish: completions, toolbar, banner, keybindings."""


def test_command_list_has_all_commands():
    """COMMAND_LIST includes all slash commands plus /exit and /quit."""
    from deeprepo.tui.completions import COMMAND_LIST

    assert "/init" in COMMAND_LIST
    assert "/init --force" in COMMAND_LIST
    assert "/context" in COMMAND_LIST
    assert "/status" in COMMAND_LIST
    assert "/log" in COMMAND_LIST
    assert "/refresh" in COMMAND_LIST
    assert "/refresh --full" in COMMAND_LIST
    assert "/help" in COMMAND_LIST
    assert "/exit" in COMMAND_LIST
    assert "/quit" in COMMAND_LIST
    assert "exit" not in COMMAND_LIST
    assert "quit" not in COMMAND_LIST


def test_build_completer_returns_word_completer():
    """build_completer() returns a WordCompleter instance."""
    from prompt_toolkit.completion import WordCompleter
    from deeprepo.tui.completions import build_completer

    completer = build_completer()
    assert isinstance(completer, WordCompleter)


def test_shell_has_completer(tmp_path):
    """Shell instance has a completer attribute."""
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    assert shell.completer is not None


def test_shell_has_key_bindings(tmp_path):
    """Shell instance has key_bindings attribute."""
    from prompt_toolkit.key_binding import KeyBindings
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    assert isinstance(shell.key_bindings, KeyBindings)


def test_get_toolbar_includes_project_name(tmp_path):
    """Toolbar text includes project name and context age."""
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    toolbar = shell._get_toolbar()
    assert "deeprepo" in toolbar
    assert tmp_path.name in toolbar
    assert shell.state.context_age in toolbar


def test_get_toolbar_shows_prompt_count(tmp_path):
    """Toolbar reflects prompt history count after recording prompts."""
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    shell.state.record_prompt("test input", "test prompt")
    toolbar = shell._get_toolbar()
    assert "1 prompt generated" in toolbar


def test_welcome_banner_includes_version(tmp_path, capsys):
    """Welcome banner shows version string."""
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    shell._print_welcome()
    captured = capsys.readouterr()
    assert "deeprepo v" in captured.out


def test_welcome_banner_includes_ascii_art(tmp_path, capsys):
    """Welcome banner shows recognizable ASCII art logo content."""
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))
    shell._print_welcome()
    captured = capsys.readouterr()
    assert "___" in captured.out or "|_|" in captured.out or "/ _ \\" in captured.out
