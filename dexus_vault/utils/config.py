from typing import Any, Dict, List, Optional
from pydantic import BaseModel, SecretStr, Field, AliasChoices
from pydantic_settings import BaseSettings


class GeneralConfig(BaseSettings):
    log_level: str = "INFO"
    sync_interval: int = 60
    secrets_engine: str = "vault"


class MetricsConfig(BaseSettings):
    metrics_enable: bool = True
    metrics_port: int = 8000
    internal_metrics: bool = False


class DexConfig(BaseSettings):
    client_crt: Optional[str] = None
    client_key: Optional[str] = None
    ca_crt: Optional[str] = None
    dex_grpc_url: str = "127.0.0.1:5557"
    dex_max_retries: int = 20
    dex_retry_wait: int = 3


class VaultConfig(BaseSettings):
    vault_addr: str = "http://127.0.0.1:8200"
    vault_approle_role_id: Optional[str] = None
    vault_approle_secret_id: Optional[str] = None
    vault_approle_secret_path: Optional[str] = None
    vault_kubernetes_role: Optional[str] = None
    vault_kubernetes_jwt_path: str = (
        "/var/run/secrets/kubernetes.io/serviceaccount/token"
    )
    vault_kubernetes_mount_point: str = "kubernetes"
    vault_token: Optional[SecretStr] = None
    vault_cert: Optional[str] = None
    vault_cert_key: Optional[str] = None
    vault_cert_ca: Optional[bool | str] = False
    vault_ldap_username: Optional[str] = None
    vault_ldap_password: Optional[SecretStr] = None
    vault_request_timeout: int = 5
    vault_max_retries: int = 20
    vault_retry_wait: int = 3
    vault_allow_redirect: bool = False
    vault_namespace: Optional[str] = None
    vault_proxies: Optional[Dict[str, Any]] = None
    vault_mount_point: Optional[str] = None
    vault_clients_path: Optional[str] = None
    vault_engine: str = "v2"


class ClientModel(BaseModel):
    # TODO: make function for getting secret from Dex and put to secrets engine
    id: str
    secret: str
    redirect_uris: Optional[List[str]] = Field(
        default=[], validation_alias=AliasChoices("redirect_uris", "redirectUris")
    )
    trusted_peers: Optional[List[str]] = Field(
        default=[], validation_alias=AliasChoices("trusted_peers", "trustedPeers")
    )
    public: bool = False
    name: Optional[str] = ""
    logo_url: Optional[str] = Field(
        default="", validation_alias=AliasChoices("logo_url", "logoUrl")
    )
