"""
Runtime configuration.

Every setting is read from an environment variable with the same name as the
field (case-insensitive), or from a `.env` file in the working directory.
"""

from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BeforeValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _bool_or_path(value: Any) -> Any:
    """Accept true/false flags as well as a path to a CA bundle."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("", "true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    return value


def _upper(value: Any) -> Any:
    return value.upper() if isinstance(value, str) else value


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]
TlsVerify = Annotated[bool | str, BeforeValidator(_bool_or_path)]
LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    BeforeValidator(_upper),
]


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class GeneralConfig(_Settings):
    # where client definitions are read from
    secrets_backend: Literal["vault", "aws-ssm"] = "vault"
    log_level: LogLevel = "INFO"
    log_format: Literal["text", "json"] = "text"
    sync_interval: int = Field(default=60, ge=1)
    # run a single sync and exit, useful for Kubernetes Jobs/CronJobs
    sync_once: bool = False
    # log planned changes without applying them
    sync_dry_run: bool = False
    # delete Dex clients that are not defined in Vault (opt-in)
    sync_prune: bool = False
    # only prune clients whose id starts with this prefix
    sync_prune_prefix: str = ""
    # never prune these client ids
    sync_prune_exclude: CsvList = []


class MetricsConfig(_Settings):
    metrics_enable: bool = True
    # all interfaces, so Kubernetes probes and Prometheus can reach the pod;
    # the endpoints expose counts only, never client data
    metrics_addr: str = "0.0.0.0"  # nosec B104
    metrics_port: int = 8000
    internal_metrics: bool = False


class DexConfig(_Settings):
    dex_grpc_url: str = "127.0.0.1:5557"
    client_crt: str | None = Field(
        default=None, validation_alias=AliasChoices("dex_client_crt", "client_crt")
    )
    client_key: str | None = Field(
        default=None, validation_alias=AliasChoices("dex_client_key", "client_key")
    )
    ca_crt: str | None = Field(
        default=None, validation_alias=AliasChoices("dex_ca_crt", "ca_crt")
    )
    # deadline in seconds for every gRPC call
    dex_timeout: float = Field(default=10, gt=0)
    dex_max_retries: int = Field(default=20, ge=0)
    dex_retry_wait: float = Field(default=3, ge=0)


class VaultConfig(_Settings):
    vault_addr: str = "http://127.0.0.1:8200"
    vault_mount_point: str
    vault_clients_path: str
    vault_engine: Literal["v1", "v2"] = "v2"
    vault_namespace: str | None = None
    # TLS verification: true (system CA store), false, or a path to a CA bundle
    vault_cert_ca: TlsVerify = True
    vault_request_timeout: float = Field(default=10, gt=0)
    vault_allow_redirect: bool = False
    vault_proxies: dict[str, str] | None = None
    vault_max_retries: int = Field(default=20, ge=0)
    vault_retry_wait: float = Field(default=3, ge=0)

    # "auto" picks the first method that has its settings configured,
    # in this order: approle, kubernetes, ldap, cert, token
    vault_auth_method: Literal[
        "auto", "approle", "kubernetes", "ldap", "cert", "token"
    ] = "auto"
    vault_token: SecretStr | None = None
    vault_approle_role_id: str | None = None
    vault_approle_secret_id: SecretStr | None = None
    vault_approle_secret_path: str | None = None
    vault_approle_mount_point: str = "approle"
    vault_kubernetes_role: str | None = None
    vault_kubernetes_jwt_path: str = (
        "/var/run/secrets/kubernetes.io/serviceaccount/token"
    )
    vault_kubernetes_mount_point: str = "kubernetes"
    vault_ldap_username: str | None = None
    vault_ldap_password: SecretStr | None = None
    vault_ldap_mount_point: str = "ldap"
    vault_cert: str | None = None
    vault_cert_key: str | None = None
    vault_cert_role: str = ""
    vault_cert_mount_point: str = "cert"


class SsmConfig(_Settings):
    """
    AWS Systems Manager Parameter Store. Credentials come from the standard
    AWS chain: environment, shared config/SSO profile, web identity (IRSA),
    EKS Pod Identity or the instance profile.
    """

    # parameter path holding one JSON parameter per client, e.g. /dex/clients
    ssm_path: str
    aws_region: str | None = None
    aws_profile: str | None = None
    # static credentials, only needed when the AWS chain cannot provide them
    # (e.g. set in a .env file, which boto3 does not read)
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_session_token: SecretStr | None = None
    # custom endpoint, e.g. a VPC endpoint or a local emulator
    ssm_endpoint_url: str | None = None
    ssm_timeout: float = Field(default=10, gt=0)
    ssm_max_retries: int = Field(default=5, ge=1)

    @field_validator("ssm_path")
    @classmethod
    def _absolute_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("must start with '/', e.g. /dex/clients")
        return value.rstrip("/") or "/"
