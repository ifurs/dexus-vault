import urllib.error
import urllib.request

import pytest

from dexus_vault.metrics import Metrics, start_http_server
from dexus_vault.sync import SyncReport


@pytest.fixture
def server():
    metrics = Metrics(sync_interval=60)
    server = start_http_server(metrics, "127.0.0.1", 0)
    yield metrics, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_health_and_readiness(server):
    metrics, base = server
    assert get(f"{base}/healthz")[0] == 200
    assert get(f"{base}/readyz")[0] == 503
    metrics.record(SyncReport(), duration=0.1)
    assert get(f"{base}/readyz")[0] == 200
    assert get(f"{base}/nope")[0] == 404


def test_failed_sync_is_not_ready(server):
    metrics, base = server
    metrics.record(None, duration=0.1)
    assert get(f"{base}/readyz")[0] == 503


def test_counters_accumulate_across_syncs(server):
    metrics, base = server
    for _ in range(2):
        report = SyncReport(clients=3, invalid=1)
        report.operations[("create", "ok")] += 1
        metrics.record(report, duration=0.1)
    status, body = get(f"{base}/metrics")
    assert status == 200
    assert (
        'dexus_vault_client_operations_total{operation="create",status="ok"} 2.0'
        in body
    )
    assert 'dexus_vault_syncs_total{result="success"} 2.0' in body
    assert "dexus_vault_clients 3.0" in body
    assert "dexus_vault_invalid_secrets 1.0" in body
    assert 'dexus_vault_build_info{backend="vault",version="' in body
