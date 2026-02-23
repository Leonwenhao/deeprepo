"""Tests for TUI onboarding flow."""

import os

import yaml


def _patch_global_config(tmp_path, monkeypatch):
    import deeprepo.tui.onboarding as onboarding_mod

    fake_config_dir = tmp_path / ".deeprepo_global"
    fake_config_file = fake_config_dir / "config.yaml"
    monkeypatch.setattr(onboarding_mod, "GLOBAL_CONFIG_DIR", fake_config_dir)
    monkeypatch.setattr(onboarding_mod, "GLOBAL_CONFIG_FILE", fake_config_file)
    return onboarding_mod, fake_config_dir, fake_config_file


def test_needs_onboarding_all_missing(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_api_key"] is True
    assert result["needs_init"] is True


def test_needs_onboarding_has_env_key(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-from-env")

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_api_key"] is False


def test_needs_onboarding_haal_config(tmp_path, monkeypatch):
    onboarding_mod, fake_config_dir, fake_config_file = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    fake_config_dir.mkdir(parents=True)
    fake_config_file.write_text(
        yaml.safe_dump({"api_key": "sk-or-v1-from-config"}, sort_keys=False),
        encoding="utf-8",
    )

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_api_key"] is False
    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-v1-from-config"


def test_needs_onboarding_project_initialized(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-ready")

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_init"] is False


def test_needs_onboarding_nothing_needed(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-ready")

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_api_key"] is False
    assert result["needs_init"] is False


def test_load_global_api_key_missing(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)

    result = onboarding_mod.load_global_api_key()

    assert result is None


def test_load_global_api_key_present(tmp_path, monkeypatch):
    onboarding_mod, fake_config_dir, fake_config_file = _patch_global_config(tmp_path, monkeypatch)
    fake_config_dir.mkdir(parents=True)
    fake_config_file.write_text(
        yaml.safe_dump({"api_key": "sk-or-v1-present"}, sort_keys=False),
        encoding="utf-8",
    )

    result = onboarding_mod.load_global_api_key()

    assert result == "sk-or-v1-present"


def test_save_global_api_key(tmp_path, monkeypatch):
    onboarding_mod, _, fake_config_file = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    onboarding_mod.save_global_api_key("sk-or-v1-test123")

    assert fake_config_file.is_file()
    data = yaml.safe_load(fake_config_file.read_text(encoding="utf-8"))
    assert data["api_key"] == "sk-or-v1-test123"
    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-v1-test123"


def test_run_onboarding_skips_when_nothing_needed(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-ready")

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    result = onboarding_mod.run_onboarding(
        str(tmp_path),
        input_fn=lambda _prompt: (_ for _ in ()).throw(AssertionError("input_fn should not be called")),
    )

    assert result["api_key_configured"] is True
    assert result["project_initialized"] is True
    assert result["skipped"] is True


def test_run_onboarding_prompts_for_api_key(tmp_path, monkeypatch):
    onboarding_mod, _, fake_config_file = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    responses = iter(["sk-or-v1-testkey123"])
    result = onboarding_mod.run_onboarding(str(tmp_path), input_fn=lambda _prompt: next(responses))

    assert result["api_key_configured"] is True
    assert result["project_initialized"] is True
    assert result["skipped"] is False
    assert fake_config_file.is_file()


def test_run_onboarding_skip_api_key(tmp_path, monkeypatch):
    onboarding_mod, _, fake_config_file = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    responses = iter([""])
    result = onboarding_mod.run_onboarding(str(tmp_path), input_fn=lambda _prompt: next(responses))

    assert result["api_key_configured"] is False
    assert result["project_initialized"] is True
    assert result["skipped"] is False
    assert fake_config_file.exists() is False


def test_run_onboit(tmp_path, monkeypatch):
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-ready")

    responses = iter(["y"])
    result = onboarding_mod.run_onboarding(str(tmp_path), input_fn=lambda _prompt: next(responses))

    assert result["api_key_configured"] is True
    assert result["project_initialized"] is False
    assert result["skipped"] is False
