import time

from dexus_vault.src.dex_processor import DexClient
from dexus_vault.src.vault_processor import VaultClient

from dexus_vault.utils.logger import logger
from dexus_vault.utils.config import get_vault_config, get_dex_config
from dexus_vault.utils.client_parser import normalize_config
from dexus_vault.utils.files import get_cached_variable, cache_variable


def sync_dex_clients(
    dex_client: object, vault_clients: list, current_clients: set
) -> set:

    logger.info(f"Target clients {[x.get('id') for x in vault_clients]}")
    for client in vault_clients:
        dex_get_client = dex_client.get_dex_client(client_id=client.get("id"))

        if dex_get_client is not None:
            client_from_dex = normalize_config(
                dex_get_client.get("client", {})
            )  # TODO: move that logic to dex_processor
            if client.get("id") == client_from_dex.get("id"):
                print(client)
                print(client_from_dex)
                if client == client_from_dex:
                    logger.debug(f"CLIENT {client_from_dex.get('id')} already exist.")

                else:
                    logger.info(
                        f"Detected changes in {client_from_dex.get('id')} client configuration, will be recreated"
                    )
                    dex_client.delete_dex_client(client_from_dex.get("id"))
                    if client_from_dex.get("id") in current_clients:
                        current_clients.remove(client_from_dex.get("id"))

                    create_client = dex_client.create_dex_client(client)
                    if create_client is not None:
                        current_clients.add(create_client)
        else:
            logger.info(f"CLIENT {client.get('id')} not found, will be created")
            create_client = dex_client.create_dex_client(client)
            if create_client is not None:
                current_clients.add(create_client)

    for current in current_clients:
        if current not in [x.get("id") for x in vault_clients]:
            logger.warning(
                f"Client {current} not in Vault configs anymore, would be deleted!"
            )
            dex_client.delete_dex_client(current)
            current_clients.remove(current)
    return current_clients


def run():
    dex_client = DexClient(config=get_dex_config())
    logger.info(f"Dex server version {dex_client.get_dex_version()}")
    current_clients = get_cached_variable()
    while True:
        dex_client = DexClient(config=get_dex_config())
        vault_client = VaultClient(config=get_vault_config())
        client_configs = vault_client.vault_read_secrets()

        current_clients = sync_dex_clients(dex_client, client_configs, current_clients)
        cache_variable(current_clients)

        print(current_clients)
        time.sleep(15)
