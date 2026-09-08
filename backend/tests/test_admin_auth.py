from __future__ import annotations

import importlib

import pytest

admin_auth = importlib.import_module("interfaces.api.admin_auth")


@pytest.fixture(autouse=True)
def clear_admin_password_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(admin_auth.ADMIN_PASSWORD_ENV, raising=False)


def test_get_admin_password_uses_fallback_when_env_missing() -> None:
    assert admin_auth.get_admin_password() == admin_auth._FALLBACK_PASSWORD


def test_get_admin_password_strips_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(admin_auth.ADMIN_PASSWORD_ENV, "  secret-value  ")
    assert admin_auth.get_admin_password() == "secret-value"


def test_get_admin_auth_status_reports_fallback() -> None:
    status = admin_auth.get_admin_auth_status()
    assert status["envVarSet"] is False
    assert status["usingFallback"] is True
    assert status["passwordLength"] == len(admin_auth._FALLBACK_PASSWORD)


def test_get_admin_auth_status_reports_env_without_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(admin_auth.ADMIN_PASSWORD_ENV, "  railway-secret  ")
    status = admin_auth.get_admin_auth_status()
    assert status["envVarSet"] is True
    assert status["usingFallback"] is False
    assert status["passwordLength"] == len("railway-secret")
