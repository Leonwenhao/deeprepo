"""Tests for version update checks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from deeprepo import update_check


class _FakeResponse:
    """Minimal urllib response stub."""

    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def cache_path(monkeypatch, tmp_path):
    """Point update-check cache to a temp file and force plain output."""
    path = tmp_path / ".deeprepo" / "update_check.json"
    monkeypatch.setattr(update_check, "CACHE_PATH", path)
    monkeypatch.setattr(update_check, "_console", None)
    return path


def _write_cache(path, hours_ago: int, latest_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_checked = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    path.write_text(
        json.dumps(
            {
                "last_checked": last_checked.isoformat(),
                "latest_version": latest_version,
            }
        ),
        encoding="utf-8",
    )


def test_newer_version_shows_banner(monkeypatch, capsys, cache_path):
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")
    monkeypatch.setattr(
        update_check,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse({"info": {"version": "0.3.0"}}),
    )

    update_check.check_for_update()

    captured = capsys.readouterr()
    assert "Update available: 0.2.3 → 0.3.0" in captured.out
    assert "pip install --upgrade deeprepo-cli" in captured.out


def test_same_version_shows_no_banner(monkeypatch, capsys, cache_path):
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.3.0")
    monkeypatch.setattr(
        update_check,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse({"info": {"version": "0.3.0"}}),
    )

    update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert captured.err.strip() == ""


def test_timeout_fails_silently(monkeypatch, capsys, cache_path):
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")

    def _raise_timeout(*_args, **_kwargs):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(update_check, "urlopen", _raise_timeout)

    update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert captured.err.strip() == ""


def test_fresh_cache_skips_http_request(monkeypatch, capsys, cache_path):
    _write_cache(cache_path, hours_ago=1, latest_version="0.2.3")
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")
    calls = {"count": 0}

    def _unexpected_urlopen(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("HTTP request should not run with fresh cache")

    monkeypatch.setattr(update_check, "urlopen", _unexpected_urlopen)

    update_check.check_for_update()

    _ = capsys.readouterr()
    assert calls["count"] == 0


def test_stale_cache_makes_http_request(monkeypatch, capsys, cache_path):
    _write_cache(cache_path, hours_ago=25, latest_version="0.2.3")
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.3.0")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        return _FakeResponse({"info": {"version": "0.3.0"}})

    monkeypatch.setattr(update_check, "urlopen", _urlopen)

    update_check.check_for_update()

    _ = capsys.readouterr()
    assert calls["count"] == 1


def test_quiet_suppresses_banner(monkeypatch, capsys, cache_path):
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        return _FakeResponse({"info": {"version": "0.3.0"}})

    monkeypatch.setattr(update_check, "urlopen", _urlopen)

    update_check.check_for_update(quiet=True)

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert calls["count"] == 0


@pytest.mark.parametrize("env_value", ["1", "true", "yes"])
def test_env_no_update_check_suppresses_banner(monkeypatch, capsys, cache_path, env_value):
    monkeypatch.setenv("DEEPREPO_NO_UPDATE_CHECK", env_value)
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        return _FakeResponse({"info": {"version": "0.3.0"}})

    monkeypatch.setattr(update_check, "urlopen", _urlopen)

    update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert calls["count"] == 0


def test_non_tty_suppresses_banner(monkeypatch, capsys, cache_path):
    monkeypatch.setattr(update_check, "_stdout_is_tty", lambda: False)
    monkeypatch.setattr(update_check, "_get_installed_version", lambda: "0.2.3")
    calls = {"count": 0}

    def _urlopen(*_args, **_kwargs):
        calls["count"] += 1
        return _FakeResponse({"info": {"version": "0.3.0"}})

    monkeypatch.setattr(update_check, "urlopen", _urlopen)

    update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert calls["count"] == 0
