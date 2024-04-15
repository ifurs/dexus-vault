import os
from typing import Any, Dict, Optional

from dexus_vault.utils.files import load_file
from dexus_vault.utils.types import check_var_type


def _get_config_value(
    key: str, target_type: type, default: Optional[Any] = None
) -> Any:
    """
    Get the configuration value for the given key, cast it to the specified target type,
    and return the default value if the environment variable is not set.
    """
    env_value = os.getenv(key, default)
    return check_var_type(env_value, target_type)


def get_metrics_config() -> Dict[str, Any]:
    """
    Get the configuration as a dictionary, with type-checked values.
    """
    return {
        "METRICS_ENABLE": _get_config_value("METRICS_ENABLE", bool, True),
        "METRICS_PORT": _get_config_value("METRICS_PORT", int, 8000),
        "INTERNAL_METRICS": _get_config_value("INTERNAL_METRICS", bool, False),
    }


def get_dex_config() -> Dict[str, Any]:
    """
    Get the configuration as a dictionary, with type-checked values.
    """
    config = {
        "CLIENT_CRT": load_file(_get_config_value("CLIENT_CRT", str)),
        "CLIENT_KEY": load_file(_get_config_value("CLIENT_KEY", str)),
        "CA_CRT": load_file(_get_config_value("CA_CRT", str)),
        "DEX_GRPC_URL": _get_config_value("DEX_GRPC_URL", str, "127.0.0.1:5557"),
        "DEX_MAX_RETRIES": _get_config_value("DEX_MAX_RETRIES", int, 20),
        "DEX_RETRY_WAIT": _get_config_value("DEX_RETRY_WAIT", int, 3),
    }
    return config


def get_vault_config() -> Dict[str, Any]:
    """
    Get the configuration as a dictionary, with type-checked values.
    """
    # TODO: Check if it really need assignment
    config = {
        "VAULT_ADDR": _get_config_value("VAULT_ADDR", str, "http://127.0.0.1:8200"),
        "VAULT_APPROLE_ROLE_ID": _get_config_value("VAULT_APPROLE_ROLE_ID", str),
        "VAULT_APPROLE_SECRET_ID": _get_config_value("VAULT_APPROLE_SECRET_ID", str),
        "VAULT_APPROLE_SECRET_PATH": load_file(
            _get_config_value("VAULT_APPROLE_SECRET_PATH", str)
        ),
        "VAULT_KUBERNETES_ROLE": _get_config_value("VAULT_KUBERNETES_ROLE", str),
        "VAULT_KUBERNETES_JWT_PATH": _get_config_value(
            "VAULT_KUBERNETES_JWT_PATH",
            str,
            "/var/run/secrets/kubernetes.io/serviceaccount/token",
        ),
        "VAULT_KUBERNETES_MOUNT_POINT": _get_config_value(
            "VAULT_KUBERNETES_MOUNT_POINT", str, "kubernetes"
        ),
        "VAULT_TOKEN": _get_config_value("VAULT_TOKEN", str),
        "VAULT_CERT": _get_config_value("VAULT_CERT", str),
        "VAULT_CERT_KEY": _get_config_value("VAULT_CERT_KEY", str),
        "VAULT_CERT_CA": _get_config_value("VAULT_CERT_CA", bool | str, False),
        "VAULT_LDAP_USERNAME": _get_config_value("VAULT_LDAP_USERNAME", str),
        "VAULT_LDAP_PASSWORD": _get_config_value("VAULT_LDAP_PASSWORD", str),
        "VAULT_REQUEST_TIMEOUT": _get_config_value("VAULT_REQUEST_TIMEOUT", int, 5),
        "VAULT_MAX_RETRIES": _get_config_value("VAULT_MAX_RETRIES", int, 20),
        "VAULT_RETRY_WAIT": _get_config_value("VAULT_RETRY_WAIT", int, 3),
        "VAULT_ALLOW_REDIRECT": _get_config_value("VAULT_ALLOW_REDIRECT", bool, False),
        "VAULT_NAMESPACE": _get_config_value("VAULT_NAMESPACE", str),
        "VAULT_PROXIES": _get_config_value("VAULT_PROXIES", dict),
        "VAULT_MOUNT_POINT": _get_config_value("VAULT_MOUNT_POINT", str),
        "VAULT_CLIENTS_PATH": _get_config_value("VAULT_CLIENTS_PATH", str),
        "VAULT_ENGINE": _get_config_value("VAULT_ENGINE", str, "v2"),
    }
    return config
