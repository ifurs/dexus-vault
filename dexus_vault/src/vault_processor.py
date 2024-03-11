import hvac
import logging

from dexus_vault.utils.client_parser import normalize_config

logger = logging.getLogger()


class VaultClient:
    """
    This Class represents methods we used inside dexus_vault, nothing new, just wrap hvac
    """

    def __init__(self, config):
        self.config = config
        self.client = self.login_to_client()

    def _check_if_vault_auth(self, client: object, auth_method: str) -> None:
        """
        Function validates if we sucessfuly authentificated to Vault
        """
        if client.is_authenticated():
            logger.debug(
                f"Authentificated to Vault {self.config['VAULT_ADDR']} via {auth_method} auth method"
            )
        else:
            raise RuntimeError(
                f"Failed to authentificate to Vault {self.config['VAULT_ADDR']} via {auth_method} auth method "
            )

    def login_to_client(self) -> object:
        """
        Define auth method for Vault and authentificate
        """

        client = hvac.Client(url=self.config["VAULT_ADDR"])

        if self.config["VAULT_APPROLE"] is not None:
            auth_method = "approle"
            client.sys.enable_auth_method(
                method_type=self.auth_method,
            )

            if self.config["VAULT_APPROLE_ROLE_ID"]:
                client.auth.approle.login(
                    role_id=self.config["VAULT_APPROLE_ROLE_ID"],
                    secret_id=self.config["VAULT_APPROLE_SECRET_ID"],
                )

            elif self.config["VAULT_APPROLE_PATH"]:
                client.sys.enable_auth_method(
                    method_type=self.auth_method,
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
            raise KeyError(f"AUTH method not specified!")

        self._check_if_vault_auth(client, auth_method)
        return client

    def vault_list_secrets(self) -> list:
        """
        List secrets from Vault by path
        """
        response = self.client.secrets.kv.v2.list_secrets(
            self.config["VAULT_CLIENTS_PATHS"],
            mount_point=self.config["VAULT_MOUNT_POINT"],
        )
        return response["data"]["keys"]

    def vault_read_secret(self, secret_path: str):
        """
        Read specified secret from Vault
        """
        response = self.client.secrets.kv.read_secret_version(
            path=f"{self.config['VAULT_CLIENTS_PATHS']}/{secret_path}",
            mount_point=self.config["VAULT_MOUNT_POINT"],
        )
        return response["data"]["data"]

    def vault_read_secrets(self) -> list:
        """Combine list_secrets with read_secret"""

        _client_config = []
        for secret in self.vault_list_secrets():
            config = normalize_config(self.vault_read_secret(secret_path=secret))
            if config is not None:
                _client_config.append(config)

            else:
                logger.warning(
                    f"Secret '{secret}' in Vault, missing 'id' and 'secret' keys, or have incorrect structure"
                )
        return _client_config
