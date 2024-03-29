import os
import time

from dexus_vault.src.dex_processor import DexClient
from dexus_vault.src.vault_processor import VaultClient

from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import start_metrics_server
from dexus_vault.utils.config import (
    get_vault_config,
    get_dex_config,
    get_metrics_config,
)
from dexus_vault.utils.client_parser import normalize_config


SYNC_INTERVAL = os.getenv("SYNC_INTERVAL", 60)


def metrics_server():
    """
    Start the Prometheus metrics server.
    """
    metrics_config = get_metrics_config()
    start_metrics_server(
        metrics_config.get("INTERNAL_METRICS"),
        metrics_config.get("METRICS_ENABLE"),
        metrics_config.get("METRICS_PORT"),
    )


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
                    logger.debug(f"Client '{client_from_dex.get('id')}' already exist.")

                else:
                    logger.info(
                        f"Detected changes in '{client_from_dex.get('id')}' client configuration, will be recreated"
                    )
                    dex_client.delete_dex_client(client_from_dex.get("id"))
                    dex_client.create_dex_client(client)
        else:
            logger.info(f"Client '{client.get('id')}' not found, will be created")
            dex_client.create_dex_client(client)


def run():
    """
    Main function to run the Dex client and Vault client synchronization.
    """

    dex_client = DexClient(config=get_dex_config())
    metrics_server()
    dex_client.dex_waiter()

    while True:

        dex_client = DexClient(config=get_dex_config())
        vault_client = VaultClient(config=get_vault_config())
        client_configs = vault_client.vault_read_secrets()

        sync_dex_clients(dex_client, client_configs)
        logger.info(f"Sync completed, next sync after {SYNC_INTERVAL} seconds")
        time.sleep(SYNC_INTERVAL)
