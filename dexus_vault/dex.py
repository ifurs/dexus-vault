"""
Thin wrapper around the Dex gRPC API.
"""

import threading

import grpc

import dexus_vault.grpc_dexidp.dexidp.api_pb2 as pb2
from dexus_vault.config import DexConfig
from dexus_vault.grpc_dexidp.dexidp.api_pb2_grpc import DexStub
from dexus_vault.log import logger
from dexus_vault.models import Client

# Dex API versions reported by GetVersion
API_LIST_CLIENTS = 3  # Dex v2.44.0
API_EXTENDED_FIELDS = 4  # Dex v2.46.0


class DexError(Exception):
    pass


def _read(path: str | None) -> bytes | None:
    if not path:
        return None
    with open(path, "rb") as file:
        return file.read()


def _is_not_found(error: grpc.RpcError) -> bool:
    # Dex returns storage.ErrNotFound as a plain error, so it arrives as UNKNOWN
    if error.code() == grpc.StatusCode.NOT_FOUND:
        return True
    return error.code() == grpc.StatusCode.UNKNOWN and "not found" in (
        error.details() or ""
    )


class DexAPI:
    def __init__(self, config: DexConfig):
        self.config = config
        self.server_version = ""
        self.api_version = 0
        self._channel = self._open_channel()
        self._stub = DexStub(self._channel)

    def _open_channel(self) -> grpc.Channel:
        config = self.config
        if bool(config.client_crt) != bool(config.client_key):
            raise DexError("Dex client certificate and key must be set together")

        if config.client_crt or config.ca_crt:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=_read(config.ca_crt),
                private_key=_read(config.client_key),
                certificate_chain=_read(config.client_crt),
            )
            logger.debug(f"Connecting to Dex {config.dex_grpc_url} over TLS")
            return grpc.secure_channel(config.dex_grpc_url, credentials)

        logger.warning(
            f"Connecting to Dex {config.dex_grpc_url} without TLS, "
            "set DEX_CA_CRT (and DEX_CLIENT_CRT/DEX_CLIENT_KEY for mTLS)"
        )
        return grpc.insecure_channel(config.dex_grpc_url)

    def _call(self, method: str, request, what: str):
        try:
            return getattr(self._stub, method)(request, timeout=self.config.dex_timeout)
        except grpc.RpcError as error:
            raise DexError(f"{what}: {error.code().name}: {error.details()}") from error

    @property
    def supports_list(self) -> bool:
        return self.api_version >= API_LIST_CLIENTS

    @property
    def supports_extended_fields(self) -> bool:
        return self.api_version >= API_EXTENDED_FIELDS

    def get_version(self) -> str:
        response = self._call("GetVersion", pb2.VersionReq(), "get version")
        self.server_version = response.server
        self.api_version = response.api
        return response.server

    def wait_ready(self, stop: threading.Event | None = None) -> None:
        """
        Wait until Dex answers, retrying DEX_MAX_RETRIES times.
        """
        stop = stop or threading.Event()
        attempt = 0
        while True:
            try:
                self.get_version()
                logger.info(
                    f"Connected to Dex {self.server_version} (API {self.api_version})"
                )
                if not self.supports_list:
                    logger.warning(
                        "Dex older than v2.44.0 has no ListClients, pruning is disabled"
                    )
                if not self.supports_extended_fields:
                    logger.info(
                        "Dex older than v2.46.0, these client fields are ignored: "
                        "allowed_connectors, sso_shared_with, backchannel_logout_uri, "
                        "post_logout_redirect_uris, refresh_token_lifetime"
                    )
                return
            except DexError as error:
                if attempt >= self.config.dex_max_retries:
                    raise DexError(f"Dex is unreachable: {error}") from error
                attempt += 1
                logger.warning(
                    f"Dex is unavailable ({error}), "
                    f"retry {attempt}/{self.config.dex_max_retries}"
                )
                if stop.wait(self.config.dex_retry_wait):
                    raise DexError("interrupted while waiting for Dex") from None

    def get_client(self, client_id: str) -> Client | None:
        try:
            response = self._stub.GetClient(
                pb2.GetClientReq(id=client_id), timeout=self.config.dex_timeout
            )
        except grpc.RpcError as error:
            if _is_not_found(error):
                return None
            raise DexError(
                f"get client '{client_id}': {error.code().name}: {error.details()}"
            ) from error
        return Client.from_proto(response.client)

    def list_client_ids(self) -> list[str]:
        response = self._call("ListClients", pb2.ListClientReq(), "list clients")
        return [client.id for client in response.clients]

    def create_client(self, client: Client) -> None:
        response = self._call(
            "CreateClient",
            pb2.CreateClientReq(client=client.to_proto()),
            f"create client '{client.id}'",
        )
        if response.already_exists:
            raise DexError(f"create client '{client.id}': already exists")

    def update_client(self, client: Client) -> None:
        response = self._call(
            "UpdateClient", client.to_update_request(), f"update client '{client.id}'"
        )
        if response.not_found:
            raise DexError(f"update client '{client.id}': not found")

    def delete_client(self, client_id: str) -> bool:
        """
        Delete a client, returns False if it did not exist.
        """
        response = self._call(
            "DeleteClient",
            pb2.DeleteClientReq(id=client_id),
            f"delete client '{client_id}'",
        )
        return not response.not_found

    def close(self) -> None:
        self._channel.close()
