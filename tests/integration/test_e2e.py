"""
End-to-end tests against real Dex and Vault, started with:

    docker/tests/start.sh up
    DEXUS_INTEGRATION=1 pytest tests/integration
"""

import os
import subprocess
import sys
import uuid

import hvac
import pytest

from dexus_vault.config import DexConfig, VaultConfig
from dexus_vault.dex import DexAPI
from dexus_vault.sync import Syncer, SyncOptions
from dexus_vault.vault import VaultSource

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DEXUS_INTEGRATION"), reason="set DEXUS_INTEGRATION=1"
    ),
]

VAULT_ADDR = os.environ.get("IT_VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.environ.get("IT_VAULT_TOKEN", "root")
DEX_GRPC_URL = os.environ.get("IT_DEX_GRPC_URL", "127.0.0.1:5557")
MOUNT = "secret"  # KV v2 engine of the Vault dev server


@pytest.fixture
def prefix():
    return f"it-{uuid.uuid4().hex[:8]}-"


@pytest.fixture
def env(prefix, monkeypatch):
    values = {
        "VAULT_ADDR": VAULT_ADDR,
        "VAULT_TOKEN": VAULT_TOKEN,
        "VAULT_MOUNT_POINT": MOUNT,
        "VAULT_CLIENTS_PATH": prefix.rstrip("-"),
        "DEX_GRPC_URL": DEX_GRPC_URL,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture
def kv(env):
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    path = env["VAULT_CLIENTS_PATH"]

    class KV:
        def put(self, key, data):
            client.secrets.kv.v2.create_or_update_secret(
                path=f"{path}/{key}", secret=data, mount_point=MOUNT
            )

        def delete(self, key):
            client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=f"{path}/{key}", mount_point=MOUNT
            )

    yield KV()
    for key in client.secrets.kv.v2.list_secrets(path=path, mount_point=MOUNT)["data"][
        "keys"
    ]:
        KV().delete(key)


@pytest.fixture
def dex(env, prefix):
    api = DexAPI(DexConfig(_env_file=None))
    api.wait_ready()
    yield api
    for client_id in api.list_client_ids():
        if client_id.startswith(prefix):
            api.delete_client(client_id)
    api.close()


@pytest.fixture
def syncer(env, dex, prefix):
    vault = VaultSource(VaultConfig(_env_file=None))
    vault.connect()
    yield Syncer(dex, vault, SyncOptions(prune=True, prune_prefix=prefix))
    vault.close()


def test_full_lifecycle(kv, dex, syncer, prefix):
    app, other = f"{prefix}app", f"{prefix}other"
    kv.put("app", {"id": app, "secret": "s1", "redirect_uris": "http://a/cb"})
    kv.put("other", {"id": other, "public": True, "allowed_connectors": ["mock"]})
    kv.put("broken", {"name": "no secret"})

    report = syncer.run_once()
    assert report.ok and report.invalid == 1
    assert report.operations[("create", "ok")] == 2
    assert dex.get_client(app).redirect_uris == ["http://a/cb"]
    assert dex.get_client(other).allowed_connectors == ["mock"]

    # nothing changed, nothing to do
    report = syncer.run_once()
    assert report.unchanged == 2 and not report.operations

    # in-place update
    kv.put(
        "app",
        {"id": app, "secret": "s1", "redirect_uris": ["http://a/cb", "http://b/cb"]},
    )
    report = syncer.run_once()
    assert report.operations == {("update", "ok"): 1}
    assert dex.get_client(app).redirect_uris == ["http://a/cb", "http://b/cb"]

    # secret change needs delete and create
    kv.put("app", {"id": app, "secret": "s2", "redirect_uris": ["http://a/cb"]})
    report = syncer.run_once()
    assert report.operations == {("recreate", "ok"): 1}
    assert dex.get_client(app).secret.get_secret_value() == "s2"

    # removing the secret prunes the client, clients outside the prefix stay
    kv.delete("other")
    report = syncer.run_once()
    assert report.operations == {("delete", "ok"): 1}
    assert dex.get_client(other) is None
    assert dex.get_client(app) is not None


def test_cli_once(kv, dex, env, prefix, tmp_path):
    kv.put("cli", {"id": f"{prefix}cli", "secret": "s"})
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dexus_vault",
            "--once",
            "--env-file",
            str(tmp_path / "none"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert dex.get_client(f"{prefix}cli") is not None


def test_cli_once_fails_on_unreachable_dex(env, monkeypatch, tmp_path):
    monkeypatch.setenv("DEX_GRPC_URL", "127.0.0.1:1")
    monkeypatch.setenv("DEX_MAX_RETRIES", "0")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dexus_vault",
            "--once",
            "--env-file",
            str(tmp_path / "none"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert "Dex is unreachable" in result.stdout
