"""
Reads Dex client definitions from a Vault KV secrets engine.
"""

import threading
from typing import Any

import hvac
import hvac.exceptions
import requests

from dexus_vault.config import VaultConfig
from dexus_vault.log import logger
from dexus_vault.sources import SecretEntry, SourceError

# auth methods that obtain their own token and can log in again when it expires
LOGIN_METHODS = ("approle", "kubernetes", "ldap", "cert")


class VaultError(SourceError):
    pass


def _read_file(path: str) -> str:
    with open(path) as file:
        return file.read().strip()


class VaultSource:
    name = "vault"

    def __init__(self, config: VaultConfig, stop: threading.Event | None = None):
        self.config = config
        self.auth_method = self._select_auth_method()
        # interrupts retries on shutdown
        self._stop = stop or threading.Event()
        self._client: hvac.Client | None = None

    @property
    def _path(self) -> str:
        return self.config.vault_clients_path.strip("/")

    def _select_auth_method(self) -> str:
        config = self.config
        if config.vault_auth_method != "auto":
            return config.vault_auth_method
        if config.vault_approle_role_id:
            return "approle"
        if config.vault_kubernetes_role:
            return "kubernetes"
        if config.vault_ldap_username and config.vault_ldap_password:
            return "ldap"
        if config.vault_cert and config.vault_cert_key:
            return "cert"
        if config.vault_token:
            return "token"
        raise VaultError(
            "No Vault auth method configured, set VAULT_TOKEN, VAULT_APPROLE_ROLE_ID, "
            "VAULT_KUBERNETES_ROLE, VAULT_LDAP_USERNAME/PASSWORD or VAULT_CERT/KEY"
        )

    def _new_client(self) -> hvac.Client:
        config = self.config
        cert = None
        if config.vault_cert and config.vault_cert_key:
            cert = (config.vault_cert, config.vault_cert_key)
        return hvac.Client(
            url=config.vault_addr,
            namespace=config.vault_namespace,
            verify=config.vault_cert_ca,
            cert=cert,
            timeout=config.vault_request_timeout,
            proxies=config.vault_proxies,
            allow_redirects=config.vault_allow_redirect,
        )

    def _wait_ready(self, client: hvac.Client) -> None:
        """
        Wait until Vault is reachable, initialized and unsealed.
        """
        attempt = 0
        while True:
            try:
                status = client.sys.read_health_status(
                    method="GET",
                    standby_ok=True,
                    sealed_code=200,
                    uninit_code=200,
                    performance_standby_code=200,
                )
                if isinstance(status, requests.Response):
                    status = status.json()
                if not status.get("initialized"):
                    problem = "not initialized"
                elif status.get("sealed"):
                    problem = "sealed"
                else:
                    return
            except (requests.RequestException, hvac.exceptions.VaultError) as error:
                problem = f"unreachable ({error})"
            except ValueError as error:
                problem = f"returned an invalid health response ({error})"

            if attempt >= self.config.vault_max_retries:
                raise VaultError(f"Vault {self.config.vault_addr} is {problem}")
            attempt += 1
            logger.warning(
                f"Vault {self.config.vault_addr} is {problem}, "
                f"retry {attempt}/{self.config.vault_max_retries}"
            )
            if self._stop.wait(self.config.vault_retry_wait):
                raise VaultError("interrupted while waiting for Vault")

    def _login(self, client: hvac.Client) -> None:
        config = self.config
        method = self.auth_method
        if method == "approle":
            if config.vault_approle_secret_path:
                secret_id = _read_file(config.vault_approle_secret_path)
            elif config.vault_approle_secret_id:
                secret_id = config.vault_approle_secret_id.get_secret_value()
            else:
                secret_id = None
            client.auth.approle.login(
                role_id=config.vault_approle_role_id,
                secret_id=secret_id,
                mount_point=config.vault_approle_mount_point,
            )
        elif method == "kubernetes":
            client.auth.kubernetes.login(
                role=config.vault_kubernetes_role,
                jwt=_read_file(config.vault_kubernetes_jwt_path),
                mount_point=config.vault_kubernetes_mount_point,
            )
        elif method == "ldap":
            client.auth.ldap.login(
                username=config.vault_ldap_username,
                password=config.vault_ldap_password.get_secret_value(),
                mount_point=config.vault_ldap_mount_point,
            )
        elif method == "cert":
            if not config.vault_cert_ca:
                raise VaultError("cert auth requires TLS verification (VAULT_CERT_CA)")
            client.auth.cert.login(
                name=config.vault_cert_role,
                cert_pem=config.vault_cert,
                key_pem=config.vault_cert_key,
                mount_point=config.vault_cert_mount_point,
            )
        elif method == "token":
            if not config.vault_token:
                raise VaultError("VAULT_TOKEN is not set")
            client.token = config.vault_token.get_secret_value()

    def connect(self) -> None:
        client = self._new_client()
        self._wait_ready(client)
        try:
            self._login(client)
            authenticated = client.is_authenticated()
        except (
            hvac.exceptions.VaultError,
            requests.RequestException,
            OSError,
        ) as error:
            raise VaultError(
                f"{self.auth_method} login to Vault failed: {error}"
            ) from error
        if not authenticated:
            raise VaultError(f"{self.auth_method} login to Vault was not accepted")
        self._client = client
        logger.info(
            f"Authenticated to Vault {self.config.vault_addr} via {self.auth_method}"
        )

    def ensure_session(self, min_ttl: int = 0) -> None:
        """
        Make sure the token is valid for at least `min_ttl` seconds,
        renewing it or logging in again when possible.
        """
        if self._client is None:
            self.connect()
            return
        try:
            token = self._client.auth.token.lookup_self()["data"]
        except (hvac.exceptions.Forbidden, hvac.exceptions.Unauthorized):
            if self.auth_method not in LOGIN_METHODS:
                raise VaultError("Vault token is no longer valid") from None
            logger.info("Vault token expired, logging in again")
            self.connect()
            return
        except (hvac.exceptions.VaultError, requests.RequestException) as error:
            raise VaultError(f"Vault token lookup failed: {error}") from error

        ttl = token.get("ttl") or 0
        if ttl == 0 or ttl > min_ttl:
            # ttl 0 means the token never expires
            return
        if token.get("renewable"):
            try:
                self._client.auth.token.renew_self()
                logger.debug("Vault token renewed")
                return
            except (hvac.exceptions.VaultError, requests.RequestException) as error:
                logger.warning(f"Vault token renewal failed: {error}")
        if self.auth_method in LOGIN_METHODS:
            logger.info("Vault token is about to expire, logging in again")
            self.connect()
        else:
            logger.warning(f"Vault token expires in {ttl}s and cannot be renewed")

    def _list(self) -> list[str]:
        kv = self._client.secrets.kv
        engine = kv.v1 if self.config.vault_engine == "v1" else kv.v2
        try:
            response = engine.list_secrets(
                path=self._path, mount_point=self.config.vault_mount_point
            )
        except hvac.exceptions.InvalidPath:
            # nothing stored under the path yet
            return []
        except hvac.exceptions.Forbidden as error:
            hint = ""
            if self.config.vault_engine == "v2":
                hint = ", KV v2 needs 'list' on the metadata/ path"
            raise VaultError(
                f"Permission denied listing '{self._path}'{hint}: {error}"
            ) from error
        except (hvac.exceptions.VaultError, requests.RequestException) as error:
            raise VaultError(f"Failed to list '{self._path}': {error}") from error
        return response["data"]["keys"]

    def _read(self, key: str) -> dict[str, Any] | None:
        kv = self._client.secrets.kv
        path = f"{self._path}/{key}"
        mount_point = self.config.vault_mount_point
        try:
            if self.config.vault_engine == "v1":
                return kv.v1.read_secret(path=path, mount_point=mount_point)["data"]
            response = kv.v2.read_secret_version(
                path=path, mount_point=mount_point, raise_on_deleted_version=False
            )
        except hvac.exceptions.InvalidPath:
            # removed between list and read
            return None
        return response["data"]["data"]

    def read_secrets(self) -> list[SecretEntry]:
        """
        Read every secret under VAULT_CLIENTS_PATH. Raises VaultError if the
        path cannot be listed, unreadable secrets are reported per entry.
        """
        if self._client is None:
            raise VaultError("not connected to Vault")
        entries = []
        for key in self._list():
            if key.endswith("/"):
                logger.debug(f"Skipping sub-path '{self._path}/{key}'")
                continue
            try:
                entries.append(SecretEntry(key, self._read(key)))
            except (hvac.exceptions.VaultError, requests.RequestException) as error:
                entries.append(SecretEntry(key, None, str(error)))
        return entries

    def close(self) -> None:
        # tokens we created ourselves should not outlive the process
        if self._client is not None and self.auth_method in LOGIN_METHODS:
            try:
                self._client.auth.token.revoke_self()
                logger.debug("Vault token revoked")
            except (hvac.exceptions.VaultError, requests.RequestException) as error:
                logger.debug(f"Could not revoke Vault token: {error}")
        self._client = None
