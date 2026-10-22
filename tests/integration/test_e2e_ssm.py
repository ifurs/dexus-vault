"""
End-to-end tests of the aws-ssm backend against real Dex and the moto AWS
emulator, started with:

    docker/tests/start.sh up
    DEXUS_INTEGRATION=1 pytest tests/integration
"""

import json
import os
import subprocess
import sys
import uuid

import pytest

boto3 = pytest.importorskip("boto3")

from dexus_vault.config import DexConfig, SsmConfig  # noqa: E402
from dexus_vault.dex import DexAPI  # noqa: E402
from dexus_vault.sources.aws_ssm import SsmSource  # noqa: E402
from dexus_vault.sync import Syncer, SyncOptions  # noqa: E402

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DEXUS_INTEGRATION"), reason="set DEXUS_INTEGRATION=1"
    ),
]

SSM_ENDPOINT = os.environ.get("IT_SSM_ENDPOINT", "http://127.0.0.1:5050")
DEX_GRPC_URL = os.environ.get("IT_DEX_GRPC_URL", "127.0.0.1:5557")
REGION = "eu-west-1"


@pytest.fixture
def prefix():
    return f"it-ssm-{uuid.uuid4().hex[:8]}-"


@pytest.fixture
def env(prefix, monkeypatch):
    values = {
        "SECRETS_BACKEND": "aws-ssm",
        "SSM_PATH": f"/{prefix.rstrip('-')}/clients",
        "SSM_ENDPOINT_URL": SSM_ENDPOINT,
        "AWS_REGION": REGION,
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "DEX_GRPC_URL": DEX_GRPC_URL,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    return values


@pytest.fixture
def ssm(env):
    client = boto3.client("ssm", endpoint_url=SSM_ENDPOINT, region_name=REGION)
    path = env["SSM_PATH"]
    names = set()

    class SSM:
        def put(self, key, data, type="SecureString"):
            name = f"{path}/{key}"
            value = data if isinstance(data, str) else json.dumps(data)
            client.put_parameter(Name=name, Value=value, Type=type, Overwrite=True)
            names.add(name)

        def delete(self, key):
            client.delete_parameter(Name=f"{path}/{key}")
            names.discard(f"{path}/{key}")

    yield SSM()
    for name in names:
        client.delete_parameter(Name=name)


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
    source = SsmSource(SsmConfig(_env_file=None))
    source.connect()
    yield Syncer(dex, source, SyncOptions(prune=True, prune_prefix=prefix))
    source.close()


def test_ssm_lifecycle(ssm, dex, syncer, prefix):
    app, other = f"{prefix}app", f"{prefix}other"
    ssm.put("app", {"id": app, "secret": "s1", "redirect_uris": ["http://a/cb"]})
    ssm.put("other", {"id": other, "public": True}, type="String")
    ssm.put("broken", "not json")
    # nested parameters are not part of the path
    ssm.put("nested/deep", {"id": f"{prefix}deep", "secret": "s"})

    report = syncer.run_once()
    assert report.operations[("create", "ok")] == 2
    assert dex.get_client(app).redirect_uris == ["http://a/cb"]
    assert dex.get_client(f"{prefix}deep") is None

    ssm.put("app", {"id": app, "secret": "s2", "redirect_uris": ["http://a/cb"]})
    ssm.delete("broken")
    report = syncer.run_once()
    assert report.operations == {("recreate", "ok"): 1}
    assert dex.get_client(app).secret.get_secret_value() == "s2"

    ssm.delete("other")
    report = syncer.run_once()
    assert report.operations == {("delete", "ok"): 1}
    assert dex.get_client(other) is None


def test_cli_once_with_ssm(ssm, dex, env, prefix, tmp_path):
    ssm.put("cli", {"id": f"{prefix}cli", "secret": "s"})
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


def test_cli_requires_ssm_path(env, monkeypatch, tmp_path):
    monkeypatch.delenv("SSM_PATH")
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
    assert result.returncode == 2
    assert "SSM_PATH" in result.stderr


def test_cli_once_with_irsa_web_identity(ssm, dex, env, prefix, monkeypatch, tmp_path):
    # what the EKS pod identity webhook injects for IRSA; moto serves STS
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name)
    token = tmp_path / "token"
    token.write_text(
        "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJzeXN0ZW06c2VydmljZWFjY291bnQifQ.c2ln"
    )
    monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/dexus-vault")
    monkeypatch.setenv("AWS_WEB_IDENTITY_TOKEN_FILE", str(token))
    monkeypatch.setenv("AWS_ENDPOINT_URL_STS", SSM_ENDPOINT)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/dev/null")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/dev/null")
    ssm.put("irsa", {"id": f"{prefix}irsa", "secret": "s"})

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
    assert dex.get_client(f"{prefix}irsa") is not None
