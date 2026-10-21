import pytest
from pydantic import ValidationError

import dexus_vault.grpc_dexidp.dexidp.api_pb2 as pb2
from dexus_vault.models import Client, changed_fields, needs_recreate


def make(**kwargs):
    return Client.model_validate({"id": "app", "secret": "s3cret", **kwargs})


@pytest.mark.parametrize(
    "value, expected",
    [
        (["a", "b"], ["a", "b"]),
        ("a,b", ["a", "b"]),
        (" a , b ,", ["a", "b"]),
        ('["a", "b"]', ["a", "b"]),
        ("single", ["single"]),
        ("", []),
        (None, []),
    ],
)
def test_list_fields_accept_vault_formats(value, expected):
    assert make(redirect_uris=value).redirect_uris == expected


def test_camel_case_keys_are_accepted():
    client = make(redirectUris=["http://x"], logoUrl="logo", trustedPeers="b")
    assert client.redirect_uris == ["http://x"]
    assert client.logo_url == "logo"
    assert client.trusted_peers == ["b"]


def test_public_accepts_string_from_vault_ui():
    assert make(public="true").public is True


def test_confidential_client_requires_secret():
    with pytest.raises(ValidationError, match="non-empty 'secret'"):
        Client.model_validate({"id": "app"})
    with pytest.raises(ValidationError):
        Client.model_validate({"id": "app", "secret": ""})


def test_public_client_may_omit_secret():
    assert Client.model_validate({"id": "app", "public": True}).public


def test_secret_is_not_leaked_in_repr():
    assert "s3cret" not in repr(make())
    assert "s3cret" not in str(make())


def test_invalid_refresh_token_lifetime():
    with pytest.raises(ValidationError):
        make(refresh_token_lifetime="forever")


def test_proto_round_trip():
    client = make(
        name="App",
        redirect_uris=["http://x"],
        allowed_connectors=["github"],
        backchannel_logout_uri="http://x/logout",
        refresh_token_lifetime="session",
    )
    assert Client.from_proto(client.to_proto()) == client


def test_update_request_sets_optional_fields_even_when_empty():
    request = make().to_update_request()
    assert request.HasField("backchannel_logout_uri")
    assert request.HasField("refresh_token_lifetime")
    assert isinstance(request, pb2.UpdateClientReq)


def test_no_changes():
    assert changed_fields(make(name="a"), make(name="a")) == []


def test_changed_fields_detected():
    assert changed_fields(make(name="b", public=True), make(name="a")) == [
        "public",
        "name",
    ]


def test_empty_secret_on_public_client_is_not_compared():
    desired = Client.model_validate({"id": "app", "public": True})
    actual = Client.model_validate({"id": "app", "public": True, "secret": "x"})
    assert changed_fields(desired, actual) == []


def test_extended_fields_ignored_for_old_dex():
    desired = make(allowed_connectors=["github"])
    assert changed_fields(desired, make()) == ["allowed_connectors"]
    assert changed_fields(desired, make(), extended=False) == []


def test_refresh_token_lifetime_default_equals_standalone():
    assert changed_fields(make(refresh_token_lifetime="standalone"), make()) == []


@pytest.mark.parametrize(
    "desired, changed, expected",
    [
        (make(secret="new"), ["secret"], True),
        (make(public=True), ["public"], True),
        (make(name="new"), ["name"], False),
        (make(redirect_uris=["a"]), ["redirect_uris"], False),
        # UpdateClient cannot clear lists or strings
        (make(), ["redirect_uris"], True),
        (make(), ["name"], True),
        # ... except fields with explicit presence
        (make(), ["backchannel_logout_uri"], False),
        (make(), ["refresh_token_lifetime"], False),
    ],
)
def test_needs_recreate(desired, changed, expected):
    assert needs_recreate(desired, changed) is expected
