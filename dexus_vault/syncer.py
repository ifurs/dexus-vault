import time

from pydantic import ValidationError

from dexus_vault.src.dex_processor import DexClient
from dexus_vault.src.vault_processor import VaultClient

from dexus_vault.utils.logger import logger
from dexus_vault.utils.metrics import (
    start_metrics_server,
    current_state,
    state_counter,
    publish_metrics,
)
from dexus_vault.utils.config import (
    GeneralConfig,
    MetricsConfig,
    VaultConfig,
    DexConfig,
    ClientModel,
)


def metrics_server(config):
    """
    Start the Prometheus metrics server.
    """
    try:
        start_metrics_server(config)
    except ValidationError as error:
        logger.error(f"Failed to validate metrics variables: {error}")
    except Exception as error:
        logger.error(f"Failed to process metrics configuration: {error}")


def sync_dex_clients(dex_client: object, vault_clients: list) -> set:
    """
    Synchronize Dex clients with Vault clients.
    """

    # TODO: make current clients in memory and compare it with vault, to delete clients that are not in vault
    for vault_client in vault_clients:
        try:
            client = ClientModel(**vault_client)

        except ValidationError as error:
            logger.warning(
                f"Secret '{vault_client['id']}' in Vault, missing 'secret' or have incorrect structure"
            )
            logger.debug(f"ValidationError: {error}")
            state_counter(current_state, {"operation": "secret", "status": "failed"})
            continue

        dex_get_client = dex_client.get_dex_client(client_id=client.id)
        if dex_get_client is not None:

            try:
                client_from_dex = ClientModel(**dex_get_client)

            except ValidationError as error:
                logger.warning(
                    f"Client '{client.id}' returned from Dex have incorrect structure {error}"
                )
                # TODO: add metric for incorrect structure from Dex, TBD
                continue

            if client.id == client_from_dex.id:
                if client == client_from_dex:
                    logger.debug(f"Client '{client_from_dex.id}' already exist.")
                    # just for example, we can add more complex logic here
                    # state["clients_skipped"] += 1
                    state_counter(
                        current_state, {"operation": "update", "status": "skipped"}
                    )
                else:
                    logger.info(
                        f"Detected changes in '{client_from_dex.id}' client configuration, will be recreated"
                    )
                    delete_response = dex_client.delete_dex_client(client_from_dex.id)
                    if delete_response.get("status") == "ok":
                        create_response = dex_client.create_dex_client(client)
                        state_counter(
                            current_state,
                            {
                                "operation": "update",
                                "status": create_response.get("status"),
                            },
                        )
                    else:
                        state_counter(
                            current_state, {"operation": "update", "status": "failed"}
                        )
                        continue
        else:
            logger.info(f"Client '{client.id}' not found, will be created")
            response = dex_client.create_dex_client(client)
            state_counter(current_state, response)


def run():
    """
    Main function to run the Dex client and Vault client synchronization.
    """
    general_config = GeneralConfig()
    dex_client = DexClient(config=DexConfig())
    dex_client.dex_waiter()
    metrics_server(config=MetricsConfig())

    while True:
        # define clients
        dex_client = DexClient(config=DexConfig())
        vault_client = VaultClient(config=VaultConfig())
        # get clients from Vault
        client_configs = vault_client.vault_read_secrets()
        sync_dex_clients(dex_client, client_configs)
        logger.info(
            f"Sync completed, next sync after {general_config.sync_interval} seconds"
        )
        # Publish metrics with current state to Prometheus, then reset state
        publish_metrics(current_state)
        # Wait for next sync
        time.sleep(general_config.sync_interval)
