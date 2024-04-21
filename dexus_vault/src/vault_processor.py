import sys
import time
import requests
from pydantic import ValidationError

from hvac.api.auth_methods import Kubernetes
import hvac

# from dexus_vault.utils.client_parser import normalize_config
from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import vault_client_secret_metric
from dexus_vault.utils.config import ClientModel


class VaultClient:
    """
    This Class represents methods used inside dexus_vault, nothing new, just wrap hvac
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = self.login_to_client()

    def _check_vault_status(self, client: object) -> None:
        """
        Function validates if Vault is up and running
        """

        for _ in range(self.config.vault_max_retries):
            try:
                response = client.sys.read_health_status(method="GET")
                if isinstance(response, requests.Response):
                    status = response.json()
                else:
                    status = response
                if status["initialized"]:
                    logger.debug(f"Vault {self.config.vault_addr} is initialized")
                    return True
                else:
                    logger.warning(
                        f"Vault {self.config.vault_addr} is not initialized {status}"
                    )
            except requests.exceptions.ConnectionError:
                logger.warning(f"Vault {self.config.vault_addr} connection failed")
            time.sleep(self.config.vault_addr)
        logger.error(f"Vault {self.config.vault_addr} unreachable, exiting...")
        sys.exit(1)

    def _check_if_vault_auth(self, client: object, auth_method: str) -> None:
        """
        Function validates if we successfully authenticated to Vault
        """

        if client.is_authenticated():
            logger.debug(
                f"Authenticated to Vault {self.config.vault_addr} via {auth_method} auth method"
            )

        else:
            raise RuntimeError(
                f"Failed to authenticate to Vault {self.config.vault_addr} via {auth_method} auth method "
            )

    def login_to_client(self) -> object:
        """
        Define auth method for Vault and authenticate
        """
        client = hvac.Client(url=self.config.vault_addr)
        self._check_vault_status(client)

        if self.config.vault_approle_role_id and self.config.vault_approle_secret_id:
            auth_method = "approle"

            if self.config.vault_approle_secret_path is not None:
                with self.config.vault_approle_secret_path.open("r") as secret_id:
                    client.auth.approle.login_by_approle_path(
                        role_id=self.config.vault_approle_role_id,
                        secret_id=secret_id.read(),
                    )
            else:
                client.auth.approle.login(
                    role_id=self.config.vault_approle_role_id,
                    secret_id=self.config.vault_approle_secret_id,
                )

        elif self.config.vault_kubernetes_role is not None:
            # POST /auth/{mount_point}/login
            auth_method = "kubernetes"

            with open(self.config.vault_kubernetes_jwt_path, "r") as jwt:
                # it is required to have params order mp, role, jwt
                Kubernetes(client.adapter).login(
                    mount_point=self.config.vault_kubernetes_mount_point,
                    role=self.config.vault_kubernetes_role,
                    jwt=jwt.read(),
                )

        elif self.config.vault_ldap_username and self.config.vault_ldap_password:
            auth_method = "ldap"
            client.auth.ldap.login(
                username=self.config.vault_ldap_username,
                password=self.config.vault_ldap_password.get_secret_value(),
            )

        elif self.config.vault_cert and self.config.vault_cert_key:
            auth_method = "cert"
            if self.config.vault_cert_ca:
                with open(self.config.vault_cert_ca, "r") as ca:
                    client = hvac.Client(
                        url=self.config.vault_addr,
                        cert=(self.config.vault_cert, self.config.vault_cert_key),
                        verify=ca,
                    )
            else:
                client = hvac.Client(
                    url=self.config.vault_addr,
                    token=self.config.vault_token.get_secret_value(),
                    cert=(self.config.vault_cert, self.config.vault_cert_key),
                    verify=(self.config.vault_cert_ca),
                )
                logger.debug(
                    f"Vault client auth method: {auth_method}, but CA verification is disabled"
                )

        elif self.config.vault_token is not None:
            auth_method = "token"
            client.token = self.config.vault_token.get_secret_value()

        else:
            raise KeyError(f"Vault auth method is not specified, or not supported")

        self._check_if_vault_auth(client, auth_method)
        return client

    def vault_list_secrets(self) -> list:
        """
        List secrets from Vault by path
        """

        if self.config.vault_engine == "v1":
            response = self.client.secrets.kv.v1.list_secrets(
                self.config.vault_clients_path,
                mount_point=self.config.vault_mount_point,
            )

        elif self.config.vault_engine == "v2":
            response = self.client.secrets.kv.v2.list_secrets(
                self.config.vault_clients_path,
                mount_point=self.config.vault_mount_point,
            )
        return response["data"]["keys"]

    def vault_read_secret(self, secret_path: str):
        """
        Read specified secret from Vault
        """

        if self.config.vault_engine == "v1":
            response = self.client.secrets.kv.v1.read_secret(
                path=f"{self.config.vault_clients_path}/{secret_path}",
                mount_point=self.config.vault_mount_point,
            )
            return response["data"]

        elif self.config.vault_engine == "v2":
            response = self.client.secrets.kv.read_secret_version(
                path=f"{self.config.vault_clients_path}/{secret_path}",
                mount_point=self.config.vault_mount_point,
            )
            return response["data"]["data"]
        return None

    def vault_read_secrets(self) -> list:
        """
        Combine list_secrets with read_secret
        """
        _client_config = []

        for secret in self.vault_list_secrets():
            # try:
            #     client_def = self.vault_read_secret(secret_path=secret)
            #     client_def["vault_secret_name"] = secret
            #     config = ClientModel(
            #         **client_def
            #     )
            # except ValidationError as error:
            #     logger.warning(
            #         f"Vault secret '{secret}' have incorrect structure {error}"
            #     )
            #     vault_client_secret_metric.labels(status="failed").inc()
            #     continue
            try:
                config = self.vault_read_secret(secret_path=secret)
                if config is not None:
                    if config.get("id", None) is None:
                        config["id"] = secret
                        logger.debug(f"Client id is set to secret name '{secret}'")
                    else:
                        logger.debug(f"Client id is '{config.get('id')}'")
                # print(config)
                # print(ClientModel(**config).model_dump())
            except ValidationError as error:
                logger.warning(f"Vault secret '{secret}' have incorrect structure")
                logger.debug(f"Validation error: {error}")
                vault_client_secret_metric.labels(status="failed").inc()
                continue

            if config is not None:
                _client_config.append(config)
                vault_client_secret_metric.labels(status="ok").inc()

            else:
                logger.warning(
                    f"Secret '{secret}' in Vault, missing 'secret' key, or have incorrect structure"
                )
                vault_client_secret_metric.labels(status="failed").inc()

        return _client_config
