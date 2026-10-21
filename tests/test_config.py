import pytest
from pydantic import ValidationError

from dexus_vault.config import DexConfig, GeneralConfig, VaultConfig


@pytest.fixture(autouse=True)
def vault_env(monkeypatch):
    monkeypatch.setenv("VAULT_MOUNT_POINT", "kv")
    monkeypatch.setenv("VAULT_CLIENTS_PATH", "dex")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("false", False),
        ("False", False),
        ("0", False),
        ("true", True),
        ("", True),
        ("/etc/ssl/ca.pem", "/etc/ssl/ca.pem"),
    ],
)
def test_vault_cert_ca(monkeypatch, value, expected):
    monkeypatch.setenv("VAULT_CERT_CA", value)
    assert VaultConfig(_env_file=None).vault_cert_ca == expected


def test_vault_tls_verification_is_on_by_default():
    assert VaultConfig(_env_file=None).vault_cert_ca is True


def test_vault_paths_are_required(monkeypatch):
    monkeypatch.delenv("VAULT_CLIENTS_PATH")
    with pytest.raises(ValidationError):
        VaultConfig(_env_file=None)


def test_vault_engine_is_validated(monkeypatch):
    monkeypatch.setenv("VAULT_ENGINE", "v3")
    with pytest.raises(ValidationError):
        VaultConfig(_env_file=None)


def test_log_level_is_case_insensitive_and_validated(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert GeneralConfig(_env_file=None).log_level == "DEBUG"
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError):
        GeneralConfig(_env_file=None)


def test_prune_exclude_is_comma_separated(monkeypatch):
    monkeypatch.setenv("SYNC_PRUNE_EXCLUDE", "a, b,,c")
    assert GeneralConfig(_env_file=None).sync_prune_exclude == ["a", "b", "c"]


def test_dex_certs_accept_new_and_legacy_names(monkeypatch):
    monkeypatch.setenv("CLIENT_CRT", "/legacy.crt")
    monkeypatch.setenv("DEX_CA_CRT", "/new-ca.crt")
    config = DexConfig(_env_file=None)
    assert config.client_crt == "/legacy.crt"
    assert config.ca_crt == "/new-ca.crt"
