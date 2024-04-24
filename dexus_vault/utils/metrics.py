from prometheus_client import (
    start_http_server,
    Gauge,
    REGISTRY,
    PROCESS_COLLECTOR,
    PLATFORM_COLLECTOR,
)
from dexus_vault.utils.logger import logger

"""
Define the Prometheus metrics and start the metrics server.
"""

client_create_metric = Gauge("client_create", "Client creation status", ["status"])
client_delete_metric = Gauge("client_delete", "Client deletion status", ["status"])
client_update_metric = Gauge("client_update", "Client update status", ["status"])
client_skip_metric = Gauge("client_skip", "Clients skipped to sync")
incorrect_secrets_metric = Gauge(
    "incorrect_secrets",
    "Number of wrong secrets specifications in secret engine",
)

# TODO: research if pydantic can cover that
current_state = {
    "incorrect_secrets": 0,
    "clients_skipped": 0,
    "clients_created": 0,
    "clients_deleted": 0,
    "clients_updated": 0,
    "clients_delete_failed": 0,
    "clients_create_failed": 0,
    "clients_update_failed": 0,
}


def reset_state(state):
    """
    Reset the state.
    """
    for key in state.keys():
        state[key] = 0
    logger.debug("State metrics has been reset")


def state_counter(state: dict, response: dict) -> dict:
    """
    Increment the state counter.
    """
    # Count deleted
    if response["operation"] == "delete":
        if response["status"] == "ok":
            state["clients_deleted"] += 1
        elif response["status"] == "failed":
            state["clients_delete_failed"] += 1

    # Count created
    elif response["operation"] == "create":
        if response["status"] == "ok":
            state["clients_created"] += 1
        elif response["status"] == "skipped":
            state["clients_skipped"] += 1
        elif response["status"] == "failed":
            state["clients_create_failed"] += 1

    # Count updated
    elif response["operation"] == "update":
        if response["status"] == "ok":
            state["clients_updated"] += 1
        # that's because 'get' client returned None, but on create we got {alreadyExists: True}
        elif response["status"] == "skipped":
            state["clients_skipped"] += 1
        elif response["status"] == "failed":
            state["clients_create_failed"] += 1

    # Count secrets
    elif response["operation"] == "secret":
        if response["status"] == "ok":
            logger.debug(
                "Secrets are not counted in state yet, check discussions github repo"
            )
        elif response["status"] == "failed":
            state["incorrect_secrets"] += 1
    else:
        logger.debug("No state to update on response {response}")

    logger.debug(f"Current updated: {state}")
    return state


def publish_metrics(state: dict) -> None:
    """
    Route the state to correct metric.
    """
    try:
        client_create_metric.labels(status="ok").set(state["clients_created"])
        client_create_metric.labels(status="failed").set(state["clients_create_failed"])
        client_delete_metric.labels(status="ok").set(state["clients_deleted"])
        client_delete_metric.labels(status="failed").set(state["clients_delete_failed"])
        client_update_metric.labels(status="ok").set(state["clients_updated"])
        client_update_metric.labels(status="failed").set(state["clients_update_failed"])
        client_skip_metric.set(state["clients_skipped"])
        incorrect_secrets_metric.set(state["incorrect_secrets"])
        logger.debug("Metrics published with state {state}")
    except:
        logger.warning("Failed to update state, got value: {state}")
    # we need to reset anyway
    reset_state(state)


def start_metrics_server(config) -> None:
    """
    Start the Prometheus metrics server on the specified port.
    """
    if not config.internal_metrics:
        # Unregister default metrics
        REGISTRY.unregister(PROCESS_COLLECTOR)
        REGISTRY.unregister(PLATFORM_COLLECTOR)
        REGISTRY.unregister(
            REGISTRY._names_to_collectors["python_gc_collections_total"]
        )
        logger.debug("Internal metrics disabled")
    else:
        logger.debug("Internal metrics enabled")

    if config.metrics_enable:
        start_http_server(config.metrics_port)
        logger.info(f"Prometheus metrics server started on port {config.metrics_port}")
