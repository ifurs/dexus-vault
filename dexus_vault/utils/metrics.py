from prometheus_client import (
    start_http_server,
    Counter,
    REGISTRY,
    PROCESS_COLLECTOR,
    PLATFORM_COLLECTOR,
)
from dexus_vault.utils.logger import logger

"""
Define the Prometheus metrics and start the metrics server.
"""

client_create_metric = Counter("client_create", "Client creation status", ["status"])
client_delete_metric = Counter("client_delete", "Client deletion status", ["status"])
vault_client_secret = Counter(
    "vault_client_secret",
    "Number of wrong client specifications in Vault",
    ["status"],
)
# SYNC_TIME = Summary("sync_time_seconds", "Time spent on synchronization")


def start_metrics_server(
    disable_internal_metrics: bool, start_server: bool, port: int
) -> None:
    """
    Start the Prometheus metrics server on the specified port.
    """
    if not disable_internal_metrics:
        # Unregister default metrics
        REGISTRY.unregister(PROCESS_COLLECTOR)
        REGISTRY.unregister(PLATFORM_COLLECTOR)
        REGISTRY.unregister(
            REGISTRY._names_to_collectors["python_gc_collections_total"]
        )
        logger.debug("Internal metrics disabled")

    if start_server:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
