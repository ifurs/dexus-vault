from unittest import mock

import hvac.exceptions
import pytest

from dexus_vault.config import VaultConfig
from dexus_vault.vault import SecretEntry, VaultError, VaultSource


def config(**kwargs):
    values = {"vault_mount_point": "kv", "vault_clients_path": "/dex/", **kwargs}
    return VaultConfig(_env_file=None, **values)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("VAULT_TOKEN", "VAULT_ADDR", "VAULT_NAMESPACE"):
        monkeypatch.delenv(name, raising=False)


def connected(source, client):
    source._client = client
    return source


@pytest.mark.parametrize(
    "settings, expected",
    [
        ({"vault_token": "t"}, "token"),
        ({"vault_token": "t", "vault_approle_role_id": "r"}, "approle"),
        ({"vault_token": "t", "vault_kubernetes_role": "k"}, "kubernetes"),
        ({"vault_ldap_username": "u", "vault_ldap_password": "p"}, "ldap"),
        ({"vault_cert": "c", "vault_cert_key": "k"}, "cert"),
        ({"vault_token": "t", "vault_auth_method": "ldap"}, "ldap"),
    ],
)
def test_auth_method_selection(settings, expected):
    assert VaultSource(config(**settings)).auth_method == expected


def test_no_auth_method_is_an_error():
    with pytest.raises(VaultError, match="No Vault auth method"):
        VaultSource(config())


def test_client_options_are_wired():
    source = VaultSource(
        config(
            vault_token="t",
            vault_namespace="team",
            vault_cert_ca="/ca.pem",
            vault_request_timeout=7,
        )
    )
    with mock.patch("dexus_vault.vault.hvac.Client") as client_cls:
        source._new_client()
    kwargs = client_cls.call_args.kwargs
    assert kwargs["namespace"] == "team"
    assert kwargs["verify"] == "/ca.pem"
    assert kwargs["timeout"] == 7


def test_approle_secret_file_is_stripped(tmp_path):
    secret_file = tmp_path / "secret-id"
    secret_file.write_text("abc\n")
    source = VaultSource(
        config(vault_approle_role_id="role", vault_approle_secret_path=str(secret_file))
    )
    client = mock.Mock()
    source._login(client)
    client.auth.approle.login.assert_called_once_with(
        role_id="role", secret_id="abc", mount_point="approle"
    )


def test_read_secrets_v2():
    client = mock.Mock()
    client.secrets.kv.v2.list_secrets.return_value = {
        "data": {"keys": ["app", "nested/", "deleted", "denied"]}
    }

    def read(path, mount_point, raise_on_deleted_version):
        if path == "dex/denied":
            raise hvac.exceptions.Forbidden("permission denied")
        data = None if path == "dex/deleted" else {"secret": "s"}
        return {"data": {"data": data}}

    client.secrets.kv.v2.read_secret_version.side_effect = read
    source = connected(VaultSource(config(vault_token="t")), client)

    entries = source.read_secrets()
    client.secrets.kv.v2.list_secrets.assert_called_once_with(
        path="dex", mount_point="kv"
    )
    assert entries[:2] == [
        SecretEntry("app", {"secret": "s"}),
        SecretEntry("deleted", None),
    ]
    assert entries[2].key == "denied" and "permission denied" in entries[2].error


def test_read_secrets_v1():
    client = mock.Mock()
    client.secrets.kv.v1.list_secrets.return_value = {"data": {"keys": ["app"]}}
    client.secrets.kv.v1.read_secret.return_value = {"data": {"secret": "s"}}
    source = connected(VaultSource(config(vault_token="t", vault_engine="v1")), client)
    assert source.read_secrets() == [SecretEntry("app", {"secret": "s"})]


def test_missing_path_is_empty_not_an_error():
    client = mock.Mock()
    client.secrets.kv.v2.list_secrets.side_effect = hvac.exceptions.InvalidPath()
    source = connected(VaultSource(config(vault_token="t")), client)
    assert source.read_secrets() == []


def test_list_permission_error_raises():
    client = mock.Mock()
    client.secrets.kv.v2.list_secrets.side_effect = hvac.exceptions.Forbidden()
    source = connected(VaultSource(config(vault_token="t")), client)
    with pytest.raises(VaultError, match="metadata"):
        source.read_secrets()


def test_ensure_session_renews_expiring_token():
    client = mock.Mock()
    client.auth.token.lookup_self.return_value = {
        "data": {"ttl": 30, "renewable": True}
    }
    source = connected(VaultSource(config(vault_approle_role_id="r")), client)
    source.ensure_session(min_ttl=120)
    client.auth.token.renew_self.assert_called_once()


def test_ensure_session_keeps_long_lived_token():
    client = mock.Mock()
    client.auth.token.lookup_self.return_value = {"data": {"ttl": 0}}
    source = connected(VaultSource(config(vault_token="t")), client)
    source.ensure_session(min_ttl=120)
    client.auth.token.renew_self.assert_not_called()


def test_ensure_session_logs_in_again_when_token_is_gone():
    client = mock.Mock()
    client.auth.token.lookup_self.side_effect = hvac.exceptions.Forbidden()
    source = connected(VaultSource(config(vault_approle_role_id="r")), client)
    with mock.patch.object(source, "connect") as connect:
        source.ensure_session(min_ttl=120)
    connect.assert_called_once()


def test_ensure_session_fails_for_invalid_static_token():
    client = mock.Mock()
    client.auth.token.lookup_self.side_effect = hvac.exceptions.Forbidden()
    source = connected(VaultSource(config(vault_token="t")), client)
    with pytest.raises(VaultError, match="no longer valid"):
        source.ensure_session()


def test_close_revokes_only_tokens_we_created():
    client = mock.Mock()
    connected(VaultSource(config(vault_approle_role_id="r")), client).close()
    client.auth.token.revoke_self.assert_called_once()

    client = mock.Mock()
    connected(VaultSource(config(vault_token="t")), client).close()
    client.auth.token.revoke_self.assert_not_called()
