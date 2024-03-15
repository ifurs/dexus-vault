import os
import time

from src.dex_processor import DexClient
from src.vault_processor import VaultClient

from utils.logger import logger
from utils.config import get_vault_config, get_dex_config
from utils.client_parser import normalize_config


SYNC_INTERVAL = os.getenv("SYNC_INTERVAL", 60)
VAULT_TIMEOUT = os.getenv("VAULT_TIMEOUT", 300)


def sync_dex_clients(dex_client: object, vault_clients: list) -> set:
    """
    Synchronize Dex clients with Vault clients.
    """
    logger.debug(f"Target clients {[x.get('id') for x in vault_clients]}")
    for client in vault_clients:
        dex_get_client = dex_client.get_dex_client(client_id=client.get("id"))

        if dex_get_client is not None:
            client_from_dex = normalize_config(
                dex_get_client.get("client", {})
            )  # TODO: move that logic to dex_processor
            if client.get("id") == client_from_dex.get("id"):

                if client == client_from_dex:
                    logger.debug(f"CLIENT {client_from_dex.get('id')} already exist.")

                else:
                    logger.info(
                        f"Detected changes in {client_from_dex.get('id')} client configuration, will be recreated"
                    )
                    dex_client.delete_dex_client(client_from_dex.get("id"))
                    dex_client.create_dex_client(client)
        else:
            logger.info(f"CLIENT {client.get('id')} not found, will be created")
            print(client)
            dex_client.create_dex_client(client)


def run():
    """
    Main function to run the Dex client and Vault client synchronization.
    """
    dex_client = DexClient(config=get_dex_config())
    logger.info(f"Dex server version {dex_client.get_dex_version()}")

    while True:
        dex_client = DexClient(config=get_dex_config())
        vault_client = VaultClient(config=get_vault_config())
        client_configs = vault_client.vault_read_secrets()

        sync_dex_clients(dex_client, client_configs)
        logger.info(f"Sync completed, next sync after {SYNC_INTERVAL} seconds")
        time.sleep(SYNC_INTERVAL)
