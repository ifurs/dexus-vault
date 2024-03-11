import grpc
import logging

# Import function that transform GRPC Message into Python dict
from google.protobuf.json_format import MessageToDict

# Load GRPC Stub and Methods from pb2 defined using protobuf builder
from dexus_vault.grpc_dexidp.dexidp.api_pb2_grpc import DexStub
import dexus_vault.grpc_dexidp.dexidp.api_pb2 as pb2

logger = logging.getLogger()


class DexClient:
    """
    This class defines all logic for operating with Dex GRPC API
    """

    def __init__(self, config):
        # credentials used for Dex connection including GRPC URL
        self.config = config

        # channel credentials obj placeholder
        self.channel = self.dex_grpc_connect()

    # crete grpc connection to Dex
    def dex_grpc_connect(self):
        """Open connection to Dex GRPC"""

        if self.config["CLIENT_CRT"]:
            self.creds = grpc.ssl_channel_credentials(
                root_certificates=self.config["CA_CRT"],
                private_key=self.config["CLIENT_KEY"],
                certificate_chain=self.config["CLIENT_CRT"],
            )

            return grpc.secure_channel(
                target=self.config["DEX_GRPC_URL"], credentials=self.creds
            )
        else:
            logger.debug(f"Dex client started in insecure channel")
            return grpc.insecure_channel(target=self.config["DEX_GRPC_URL"])

    def dex_grpc_close_connection(self):
        """Close connection to Dex GRPC"""
        self.channel.close()

    def get_dex_client(self, client_id: str):
        """
        Call Get Dex Client with params
        :param client_id:
        :param self:
        :return: response code from Dex with Client Message
        """
        dex_request = pb2.GetClientReq()
        dex_request.id = client_id

        try:
            response = DexStub(self.channel).GetClient(dex_request)
            return MessageToDict(response)

        except grpc.RpcError as rpc_error:
            if rpc_error.code() == grpc.StatusCode.UNKNOWN:
                logger.warning(
                    f"RESPONSE FROM GRPC: {rpc_error.details()}, client {client_id}"
                )
            else:
                logger.warning(
                    f"GRPC CALL CODE: {rpc_error.code()} with details {rpc_error.details()}"
                )

    def get_dex_version(self):
        """
        Get Dex version
        :return: client definition in dict format
        """
        dex_request = pb2.VersionReq()
        response = DexStub(self.channel).GetVersion(dex_request)

        return MessageToDict(response)

    def create_dex_client(self, client: dict) -> dict:
        """
        Create OIDC client in Dex
        :param client: dict with all params for creating client
        :return: dict: in case of creation you will get params back, else you get error or
        """
        request = pb2.CreateClientReq()
        request.client.id = client.get("id")
        request.client.secret = client.get("secret")
        request.client.redirect_uris.extend(client.get("redirect_uris", ""))
        request.client.trusted_peers.extend(client.get("trusted_peers", ""))
        request.client.public = client.get("public", 0)
        request.client.name = client.get("name", "")
        request.client.logo_url = client.get("logo_url", "")

        response = MessageToDict(DexStub(self.channel).CreateClient(request))
        if response.get("client", None) is not None:
            client_id = response.get("client").get("id")
            logger.info(f"Created new Dex client '{client_id}'")
            return client_id

    def delete_dex_client(self, client_id: str):
        """
        Delete OIDC client in Dex
        :param client_id: str
        :return:
        """
        dex_request = pb2.DeleteClientReq()
        dex_request.id = client_id

        # Because of Dex implementation, this request returns None
        # Or simple dict {'notFound': True} so it need to be processed
        response = MessageToDict(DexStub(self.channel).DeleteClient(dex_request))

        if response.get("notFound", None) is not None:
            logger.warning(f"Client '{client_id}' not found")
        else:
            logger.info(f"client {client_id} was deleted")

    def __del__(self):
        """
        Everytime DexClient object delets, this will close GRPC connection
        """
        self.dex_grpc_close_connection()
        logger.debug(f"Dex connection closed")
