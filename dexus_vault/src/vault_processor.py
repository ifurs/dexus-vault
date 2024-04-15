import sys
import time
import requests
import hvac

from dexus_vault.utils.client_parser import normalize_config
from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import vault_client_secret


class VaultClient:
    """
    This Class represents methods we used inside dexus_vault, nothing new, just wrap hvac
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = self.login_to_client()

    def _check_vault_status(self, client: object) -> None:
        """
        Function validates if Vault is up and running
        """

        for _ in range(self.config["VAULT_MAX_RETRIES"]):
            try:
                response = client.sys.read_health_status(method="GET")
                if isinstance(response, requests.Response):
                    status = response.json()
                else:
                    status = response
                if status["initialized"]:
                    logger.debug(f"Vault {self.config['VAULT_ADDR']} is initialized")
                    return True
                else:
                    logger.warning(
                        f"Vault {self.config['VAULT_ADDR']} is not initialized {status}"
                    )
            except requests.exceptions.ConnectionError:
                logger.warning(f"Vault {self.config['VAULT_ADDR']} connection failed")
            time.sleep(self.config["VAULT_RETRY_WAIT"])
        logger.error(f"Vault {self.config['VAULT_ADDR']} unreachable, exiting...")
        sys.exit(1)

    def _check_if_vault_auth(self, client: object, auth_method: str) -> None:
        """
        Function validates if we successfully authenticated to Vault
        """

        if client.is_authenticated():
            logger.debug(
                f"Authenticated to Vault {self.config['VAULT_ADDR']} via {auth_method} auth method"
            )

        else:
            raise RuntimeError(
                f"Failed to authenticate to Vault {self.config['VAULT_ADDR']} via {auth_method} auth method "
            )

    def login_to_client(self) -> object:
        """
        Define auth method for Vault and authenticate
        """
        client = hvac.Client(url=self.config["VAULT_ADDR"])
        self._check_vault_status(client)

        if self.config["VAULT_APPROLE"] is not None:
            auth_method = "approle"
            client.sys.enable_auth_method(
                method_type=auth_method,
            )

            if self.config["VAULT_APPROLE_ROLE_ID"]:
                client.auth.approle.login(
                    role_id=self.config["VAULT_APPROLE_ROLE_ID"],
                    secret_id=self.config["VAULT_APPROLE_SECRET_ID"],
                )

            elif self.config["VAULT_APPROLE_PATH"]:
                client.sys.enable_auth_method(
                    method_type=auth_method,
                    path=self.config["VAULT_APPROLE_PATH"],
                )

        elif self.config["VAULT_LDAP_USERNAME"] is not None:
            auth_method = "LDAP"
            client.auth.ldap.login(
                username=self.config["VAULT_LDAP_USERNAME"],
                password=self.config["VAULT_LDAP_PASSWORD"],
            )

        elif self.config["VAULT_CERT"] is not None:
            auth_method = "Client cert"
            client = hvac.Client(
                url=self.config["VAULT_ADDR"],
                token=self.config["VAULT_TOKEN"],
                cert=(self.config["VAULT_CERT"], self.config["VAULT_CERT_KEY"]),
                verify=(self.config["VAULT_CERT_CA"]),
            )

        elif self.config["VAULT_TOKEN"] is not None:
            auth_method = "Vault token"
            client.token = self.config["VAULT_TOKEN"]

        else:
            raise KeyError(f"Vault auth method is not specified!")

        self._check_if_vault_auth(client, auth_method)
        return client

    def vault_list_secrets(self) -> list:
        """
        List secrets from Vault by path
        """

        if self.config["VAULT_ENGINE"] == "v1":
            response = self.client.secrets.kv.v1.list_secrets(
                self.config["VAULT_CLIENTS_PATH"],
                mount_point=self.config["VAULT_MOUNT_POINT"],
            )

        elif self.config["VAULT_ENGINE"] == "v2":
            response = self.client.secrets.kv.v2.list_secrets(
                self.config["VAULT_CLIENTS_PATH"],
                mount_point=self.config["VAULT_MOUNT_POINT"],
            )

        return response["data"]["keys"]

    def vault_read_secret(self, secret_path: str):
        """
        Read specified secret from Vault
        """

        if self.config["VAULT_ENGINE"] == "v1":
            response = self.client.secrets.kv.v1.read_secret(
                path=f"{self.config['VAULT_CLIENTS_PATH']}/{secret_path}",
                mount_point=self.config["VAULT_MOUNT_POINT"],
            )
            return response["data"]

        elif self.config["VAULT_ENGINE"] == "v2":
            response = self.client.secrets.kv.read_secret_version(
                path=f"{self.config['VAULT_CLIENTS_PATH']}/{secret_path}",
                mount_point=self.config["VAULT_MOUNT_POINT"],
            )
            return response["data"]["data"]
        return None

    def vault_read_secrets(self) -> list:
        """
        Combine list_secrets with read_secret
        """
        _client_config = []

        for secret in self.vault_list_secrets():
            config = normalize_config(
                self.vault_read_secret(secret_path=secret), secret
            )

            if config is not None:
                _client_config.append(config)
                vault_client_secret.labels(status="ok").inc()

            else:
                logger.warning(
                    f"Secret '{secret}' in Vault, missing 'secret' key, or have incorrect structure"
                )
                vault_client_secret.labels(status="failed").inc()

        return _client_config
