import time
import grpc

# Import function that transform GRPC Message into Python dict
from google.protobuf.json_format import MessageToDict

# Load GRPC Stub and Methods from pb2 defined using protobuf builder
from dexus_vault.grpc_dexidp.dexidp.api_pb2_grpc import DexStub
import dexus_vault.grpc_dexidp.dexidp.api_pb2 as pb2

from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import client_create_metric, client_delete_metric


class DexClient:
    """
    This class defines all logic for operating with Dex gRPC API
    """

    def __init__(self, config):
        # credentials used for Dex connection including GRPC URL
        self.config = config

        # channel credentials obj placeholder
        self.channel = self.dex_grpc_connect()

    # crete grpc connection to Dex
    def dex_grpc_connect(self) -> object:
        """
        Open connection to Dex gRPC
        """

        if self.config.client_crt and self.config.client_key:

            with open(self.config.ca_crt, "rb") as ca_crt, open(
                self.config.client_key, "rb"
            ) as client_key, open(self.config.client_crt, "rb") as client_crt:

                self.creds = grpc.ssl_channel_credentials(
                    root_certificates=ca_crt.read(),
                    private_key=client_key.read(),
                    certificate_chain=client_crt.read(),
                )

            return grpc.secure_channel(
                target=self.config.dex_grpc_url, credentials=self.creds
            )
        else:
            logger.debug(f"Dex client started in insecure channel")
            return grpc.insecure_channel(target=self.config.dex_grpc_url)

    def dex_grpc_close_connection(self):
        """
        Close connection to Dex gRPC
        """
        if self.channel:
            self.channel.close()

    def dex_waiter(self) -> bool:
        """
        Ensure connection to Dex gRPC
        """
        _retry = 0
        while True:
            try:
                logger.info(f"Dex server version {self.get_dex_version()}")
                return True
            except Exception as error:
                if _retry >= self.config.dex_max_retries:
                    raise RuntimeError(f"Could not connect to Dex gRPC server: {error}")
                else:
                    _retry += 1
                    logger.debug(f"Dex gRPC is unavailable, retying...")
                    time.sleep(self.config.dex_retry_wait)

    def get_dex_version(self) -> dict:
        """
        Get Dex version
        """
        dex_request = pb2.VersionReq()
        response = DexStub(self.channel).GetVersion(dex_request)

        return MessageToDict(response)

    def get_dex_client(self, client_id: str) -> dict | None:
        """
        Get Dex Client by id
        """
        dex_request = pb2.GetClientReq()
        dex_request.id = client_id

        try:
            response = DexStub(self.channel).GetClient(dex_request)
            return MessageToDict(response).get("client")

        except grpc.RpcError as rpc_error:
            if rpc_error.code() == grpc.StatusCode.UNKNOWN:
                logger.debug(
                    f"Dex gRPC response: {rpc_error.details()}, client {client_id}"
                )
            else:
                logger.warning(
                    f"Dex gRPC error code: {rpc_error.code()} with details {rpc_error.details()}"
                )

    def create_dex_client(self, client: dict) -> dict | None:
        """
        Create OIDC client in Dex
        """
        try:

            request = pb2.CreateClientReq()
            request.client.id = client.id
            request.client.secret = client.secret
            request.client.redirect_uris.extend(client.redirect_uris)
            request.client.trusted_peers.extend(client.trusted_peers)
            request.client.public = client.public
            request.client.name = client.name
            request.client.logo_url = client.logo_url

            response = MessageToDict(DexStub(self.channel).CreateClient(request))

            if response.get("client", None) is not None:
                client_id = response.get("client").get("id")
                client_create_metric.labels(status="ok").inc()
                logger.info(f"Created new Dex client '{client_id}'")
                return client_id
            elif response.get("alreadyExists", None) is not None:
                logger.info(
                    f"Client {client.id} already exists, check Vault configs for duplicates"
                )
            else:
                logger.warning(f"Dex gRPC response: {response}")

        except Exception as error:
            client_create_metric.labels(status="failed").inc()
            logger.error(f"Failed to create client {client.id}")
            logger.error(f"Dex gRPC response: {error}")

    def delete_dex_client(self, client_id: str) -> None:
        """
        Delete OIDC client in Dex
        """
        try:
            dex_request = pb2.DeleteClientReq()
            dex_request.id = client_id

            # Because of Dex implementation, this request returns None
            # Or simple dict {'notFound': True} so it need to be processed
            response = MessageToDict(DexStub(self.channel).DeleteClient(dex_request))

            if response.get("notFound", None) is not None:
                client_delete_metric.labels(status="failed").inc()
                logger.warning(f"Client '{client_id}' not found")
            else:
                client_create_metric.labels(status="ok").inc()
                logger.info(f"client {client_id} was deleted")
        except Exception as error:
            client_delete_metric.labels(status="failed").inc()
            logger.error(f"Failed to delete client {client_id}")
            logger.error(f"Dex gRPC response: {error}")

    def __del__(self):
        """
        Every time DexClient object deletes, this will close gRPC connection
        """
        self.dex_grpc_close_connection()
        logger.debug(f"Dex connection closed")
