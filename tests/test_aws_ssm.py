import pytest
from pydantic import ValidationError

pytest.importorskip("boto3")

from botocore.stub import Stubber  # noqa: E402

from dexus_vault.config import SsmConfig  # noqa: E402
from dexus_vault.sources import SecretEntry  # noqa: E402
from dexus_vault.sources.aws_ssm import SsmError, SsmSource  # noqa: E402
from dexus_vault.sync import Syncer  # noqa: E402

from .conftest import FakeDex  # noqa: E402


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    # never touch real AWS credentials or config in unit tests
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/dev/null")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/dev/null")
    for name in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_ENDPOINT_URL"):
        monkeypatch.delenv(name, raising=False)


def make_source(path="/dex/clients"):
    source = SsmSource(SsmConfig(_env_file=None, ssm_path=path, aws_region="eu-west-1"))
    source.connect()
    return source


def parameter(name, value, type="SecureString"):
    return {"Name": name, "Type": type, "Value": value, "Version": 1}


def request(token=None):
    params = {"Path": "/dex/clients", "Recursive": False, "WithDecryption": True}
    if token:
        params["NextToken"] = token
    return params


def test_path_must_be_absolute():
    with pytest.raises(ValidationError, match="must start with '/'"):
        SsmConfig(_env_file=None, ssm_path="dex/clients")


def test_path_trailing_slash_is_removed():
    assert (
        SsmConfig(_env_file=None, ssm_path="/dex/clients/").ssm_path == "/dex/clients"
    )
    assert SsmConfig(_env_file=None, ssm_path="/").ssm_path == "/"


def test_reads_and_decodes_parameters_across_pages():
    source = make_source()
    with Stubber(source._client) as stub:
        stub.add_response(
            "get_parameters_by_path",
            {
                "Parameters": [parameter("/dex/clients/b", '{"secret": "s"}')],
                "NextToken": "page2",
            },
            request(),
        )
        stub.add_response(
            "get_parameters_by_path",
            {
                "Parameters": [
                    parameter(
                        "/dex/clients/a", '{"id": "x", "public": true}', "String"
                    ),
                ]
            },
            request("page2"),
        )
        entries = source.read_secrets()
        stub.assert_no_pending_responses()
    assert entries == [
        SecretEntry("a", {"id": "x", "public": True}),
        SecretEntry("b", {"secret": "s"}),
    ]


def test_invalid_values_are_reported_without_the_value():
    source = make_source()
    with Stubber(source._client) as stub:
        stub.add_response(
            "get_parameters_by_path",
            {
                "Parameters": [
                    parameter("/dex/clients/broken", '{"secret": "hunter2",'),
                    parameter("/dex/clients/list", "a,b", "StringList"),
                ]
            },
            request(),
        )
        entries = source.read_secrets()
    assert [entry.key for entry in entries] == ["broken", "list"]
    assert all(entry.data is None for entry in entries)
    assert "not a JSON object" in entries[0].error
    assert "hunter2" not in entries[0].error


def test_access_denied_raises_with_hint():
    source = make_source()
    with Stubber(source._client) as stub:
        stub.add_client_error(
            "get_parameters_by_path",
            service_error_code="AccessDeniedException",
            service_message="not authorized",
            expected_params=request(),
        )
        with pytest.raises(SsmError, match="ssm:GetParametersByPath"):
            source.read_secrets()


def test_empty_path_returns_no_entries():
    source = make_source()
    with Stubber(source._client) as stub:
        stub.add_response("get_parameters_by_path", {"Parameters": []}, request())
        assert source.read_secrets() == []


def test_root_path_keys():
    source = make_source(path="/")
    with Stubber(source._client) as stub:
        stub.add_response(
            "get_parameters_by_path",
            {"Parameters": [parameter("/app", '{"secret": "s"}')]},
            {"Path": "/", "Recursive": False, "WithDecryption": True},
        )
        assert source.read_secrets() == [SecretEntry("app", {"secret": "s"})]


def test_static_credentials_from_settings(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY")
    config = SsmConfig(
        _env_file=None,
        ssm_path="/dex",
        aws_region="eu-west-1",
        aws_access_key_id="AKIDEXAMPLE",
        aws_secret_access_key="secret-example",
    )
    source = SsmSource(config)
    source.connect()
    credentials = source._client._request_signer._credentials
    assert credentials.access_key == "AKIDEXAMPLE"
    assert "secret-example" not in repr(config)


def test_read_before_connect_fails():
    source = SsmSource(
        SsmConfig(_env_file=None, ssm_path="/dex", aws_region="eu-west-1")
    )
    with pytest.raises(SsmError, match="not connected"):
        source.read_secrets()


def test_syncs_clients_from_ssm():
    source = make_source()
    dex = FakeDex()
    with Stubber(source._client) as stub:
        stub.add_response(
            "get_parameters_by_path",
            {
                "Parameters": [
                    parameter("/dex/clients/app", '{"secret": "s", "name": "App"}'),
                    parameter("/dex/clients/bad", "not json"),
                ]
            },
            request(),
        )
        report = Syncer(dex, source).run_once()
    assert dex.clients["app"].name == "App"
    assert report.ok
