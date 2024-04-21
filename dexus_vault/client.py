import os
import time

from dexus_vault.src.dex_processor import DexClient
from dexus_vault.src.vault_processor import VaultClient

from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import start_metrics_server
from dexus_vault.utils.config import (
    GeneralConfig,
    MetricsConfig,
    VaultConfig,
    DexConfig,
    ClientModel,
)

# from dexus_vault.utils.client_parser import normalize_config

general_config = GeneralConfig()


def metrics_server():
    """
    Start the Prometheus metrics server.
    """
    metrics_config = MetricsConfig()
    start_metrics_server(
        metrics_config.internal_metrics,
        metrics_config.metrics_enable,
        metrics_config.metrics_port,
    )


def sync_dex_clients(dex_client: object, vault_clients: list) -> set:
    """
    Synchronize Dex clients with Vault clients.
    """

    # TODO: make state in memory and compare with it
    # logger.debug(f"Target clients {[x.get('id') for x in vault_clients]}")

    for client in vault_clients:
        print(client["id"])
        dex_get_client = dex_client.get_dex_client(client_id=client["id"])

        print(dex_get_client)

        if dex_get_client is not None:

            client_from_dex = ClientModel(**dex_get_client.get("client", {}))
            if client["id"] == client_from_dex.id:

                if client == client_from_dex:
                    logger.debug(f"Client '{client_from_dex.id}' already exist.")
                    # if you see this, that means that means that I forget to remove debug statement
                    dex_client.create_dex_client(client)

                else:
                    logger.info(
                        f"Detected changes in '{client_from_dex.id}' client configuration, will be recreated"
                    )
                    dex_client.delete_dex_client(client_from_dex.id)
                    dex_client.create_dex_client(client)
        else:
            logger.info(f"Client '{client['id']}' not found, will be created")
            dex_client.create_dex_client(ClientModel(**client))


def run():
    """
    Main function to run the Dex client and Vault client synchronization.
    """

    dex_client = DexClient(config=DexConfig())

    metrics_server()
    dex_client.dex_waiter()

    while True:
        dex_client = DexClient(config=DexConfig())
        vault_client = VaultClient(config=VaultConfig())

        client_configs = vault_client.vault_read_secrets()

        sync_dex_clients(dex_client, client_configs)
        logger.info(
            f"Sync completed, next sync after {general_config.sync_interval} seconds"
        )
        time.sleep(general_config.sync_interval)
