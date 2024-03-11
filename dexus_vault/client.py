import time

from dexus_vault.src.dex_processor import DexClient
from dexus_vault.src.vault_processor import VaultClient

from dexus_vault.utils.logger import logger
from dexus_vault.utils.config import get_vault_config, get_dex_config
from dexus_vault.utils.client_parser import normalize_config


def sync_dex_clients(dex_client: object, vault_clients: list) -> set:

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
            dex_client.create_dex_client(client)


def run():
    dex_client = DexClient(config=get_dex_config())
    logger.info(f"Dex server version {dex_client.get_dex_version()}")
    while True:
        dex_client = DexClient(config=get_dex_config())
        vault_client = VaultClient(config=get_vault_config())
        client_configs = vault_client.vault_read_secrets()

        sync_dex_clients(dex_client, client_configs)

        time.sleep(15)
