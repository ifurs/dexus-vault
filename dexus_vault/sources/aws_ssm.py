"""
Reads Dex client definitions from AWS Systems Manager Parameter Store.

Every parameter directly under SSM_PATH is one client, its value a JSON
object with the same fields as a Vault secret. SecureString parameters are
decrypted. boto3 is an optional dependency: pip install 'dexus-vault[aws]'.
"""

import json

from dexus_vault.config import SsmConfig
from dexus_vault.log import logger
from dexus_vault.sources import SecretEntry, SourceError

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - exercised only without the extra
    boto3 = None


class SsmError(SourceError):
    pass


def _secret(value) -> str | None:
    return value.get_secret_value() if value is not None else None


def _parse(value: str) -> dict:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    return data


class SsmSource:
    name = "aws-ssm"

    def __init__(self, config: SsmConfig):
        if boto3 is None:
            raise SsmError(
                "The aws-ssm backend needs boto3, install 'dexus-vault[aws]'"
            )
        self.config = config
        self._client = None

    @property
    def _prefix(self) -> str:
        return self.config.ssm_path.rstrip("/") + "/"

    def connect(self) -> None:
        config = self.config
        try:
            session = boto3.session.Session(
                profile_name=config.aws_profile,
                region_name=config.aws_region,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=_secret(config.aws_secret_access_key),
                aws_session_token=_secret(config.aws_session_token),
            )
            self._client = session.client(
                "ssm",
                endpoint_url=config.ssm_endpoint_url,
                config=Config(
                    connect_timeout=config.ssm_timeout,
                    read_timeout=config.ssm_timeout,
                    # standard mode retries throttling and transient errors
                    retries={
                        "mode": "standard",
                        "max_attempts": config.ssm_max_retries,
                    },
                ),
            )
        except BotoCoreError as error:
            raise SsmError(f"Cannot create AWS SSM client: {error}") from error
        logger.info(
            f"Reading clients from AWS SSM {config.ssm_path} "
            f"in {self._client.meta.region_name}"
        )

    def ensure_session(self, min_ttl: int = 0) -> None:
        # botocore refreshes temporary credentials on its own
        if self._client is None:
            self.connect()

    def _fetch(self) -> list[dict]:
        paginator = self._client.get_paginator("get_parameters_by_path")
        parameters = []
        try:
            for page in paginator.paginate(
                Path=self.config.ssm_path, Recursive=False, WithDecryption=True
            ):
                parameters.extend(page["Parameters"])
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            hint = ""
            if code == "AccessDeniedException":
                hint = (
                    ", needs ssm:GetParametersByPath on the path "
                    "(and kms:Decrypt for a customer managed key)"
                )
            raise SsmError(
                f"Failed to read parameters under '{self.config.ssm_path}'{hint}: {error}"
            ) from error
        except BotoCoreError as error:
            raise SsmError(
                f"Failed to read parameters under '{self.config.ssm_path}': {error}"
            ) from error
        return parameters

    def read_secrets(self) -> list[SecretEntry]:
        if self._client is None:
            raise SsmError("not connected to AWS SSM")
        entries = []
        for parameter in self._fetch():
            key = parameter["Name"].removeprefix(self._prefix)
            try:
                entries.append(SecretEntry(key, _parse(parameter["Value"])))
            except ValueError as error:
                # json errors carry positions only, never the value
                entries.append(
                    SecretEntry(key, None, f"value is not a JSON object: {error}")
                )
        return sorted(entries, key=lambda entry: entry.key)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
