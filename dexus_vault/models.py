"""
Dex client model, shared by the secret source and the Dex API wrapper.
"""

import json
from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    AliasGenerator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic.alias_generators import to_camel

import dexus_vault.grpc_dexidp.dexidp.api_pb2 as pb2


def _to_list(value: Any) -> Any:
    """
    Lists may be stored as native JSON lists, as JSON encoded
    strings ('["a", "b"]') or as comma separated strings ("a,b").
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("["):
            try:
                return json.loads(value)
            except ValueError:
                pass
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


StrList = Annotated[list[str], BeforeValidator(_to_list)]

# Fields that need Dex API version 4 (Dex v2.46.0) or newer
EXTENDED_FIELDS = (
    "allowed_connectors",
    "sso_shared_with",
    "backchannel_logout_uri",
    "post_logout_redirect_uris",
    "refresh_token_lifetime",
)
# Fields Dex cannot change in place, a change means delete and create again
RECREATE_FIELDS = ("secret", "public")
# UpdateClient treats empty values as "leave unchanged", except for these
CLEARABLE_FIELDS = ("backchannel_logout_uri", "refresh_token_lifetime")


class Client(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        alias_generator=AliasGenerator(
            validation_alias=lambda name: AliasChoices(name, to_camel(name))
        ),
    )

    id: str = Field(min_length=1)
    # empty secret on a public client means "let Dex keep whatever it has"
    secret: SecretStr = SecretStr("")
    public: bool = False
    name: str = ""
    logo_url: str = ""
    redirect_uris: StrList = []
    trusted_peers: StrList = []
    allowed_connectors: StrList = []
    sso_shared_with: StrList = []
    backchannel_logout_uri: str = ""
    post_logout_redirect_uris: StrList = []
    refresh_token_lifetime: Literal["", "standalone", "session"] = ""

    @model_validator(mode="after")
    def _confidential_needs_secret(self) -> "Client":
        # Dex generates a random secret for confidential clients created with
        # an empty one, which would never match the source and recreate it forever
        if not self.public and not self.secret.get_secret_value():
            raise ValueError("a non-public client requires a non-empty 'secret'")
        return self

    @classmethod
    def known_keys(cls) -> set[str]:
        return {key for name in cls.model_fields for key in (name, to_camel(name))}

    @classmethod
    def from_proto(cls, message: pb2.Client) -> "Client":
        # values come from Dex, so skip validation meant for user input
        return cls.model_construct(
            id=message.id,
            secret=SecretStr(message.secret),
            public=message.public,
            name=message.name,
            logo_url=message.logo_url,
            redirect_uris=list(message.redirect_uris),
            trusted_peers=list(message.trusted_peers),
            allowed_connectors=list(message.allowed_connectors),
            sso_shared_with=list(message.sso_shared_with),
            backchannel_logout_uri=message.backchannel_logout_uri,
            post_logout_redirect_uris=list(message.post_logout_redirect_uris),
            refresh_token_lifetime=message.refresh_token_lifetime,
        )

    def to_proto(self) -> pb2.Client:
        return pb2.Client(
            id=self.id,
            secret=self.secret.get_secret_value(),
            public=self.public,
            name=self.name,
            logo_url=self.logo_url,
            redirect_uris=self.redirect_uris,
            trusted_peers=self.trusted_peers,
            allowed_connectors=self.allowed_connectors,
            sso_shared_with=self.sso_shared_with,
            backchannel_logout_uri=self.backchannel_logout_uri,
            post_logout_redirect_uris=self.post_logout_redirect_uris,
            refresh_token_lifetime=self.refresh_token_lifetime,
        )

    def to_update_request(self) -> pb2.UpdateClientReq:
        return pb2.UpdateClientReq(
            id=self.id,
            name=self.name,
            logo_url=self.logo_url,
            redirect_uris=self.redirect_uris,
            trusted_peers=self.trusted_peers,
            allowed_connectors=self.allowed_connectors,
            sso_shared_with=self.sso_shared_with,
            # optional fields: always set, so an empty value clears them
            backchannel_logout_uri=self.backchannel_logout_uri,
            post_logout_redirect_uris=self.post_logout_redirect_uris,
            refresh_token_lifetime=self.refresh_token_lifetime,
        )

    def uses_extended_fields(self) -> list[str]:
        return [name for name in EXTENDED_FIELDS if getattr(self, name)]


def _comparable(client: Client, field: str) -> Any:
    value = getattr(client, field)
    if field == "secret":
        return value.get_secret_value()
    if field == "refresh_token_lifetime":
        return value or "standalone"
    return value


def changed_fields(desired: Client, actual: Client, extended: bool = True) -> list[str]:
    """
    Names of the fields that differ between the source (desired) and Dex (actual).
    With extended=False, fields unknown to older Dex servers are ignored.
    """
    changed = []
    for field in Client.model_fields:
        if field == "id" or (not extended and field in EXTENDED_FIELDS):
            continue
        if field == "secret" and not desired.secret.get_secret_value():
            continue
        if _comparable(desired, field) != _comparable(actual, field):
            changed.append(field)
    return changed


def needs_recreate(desired: Client, changed: list[str]) -> bool:
    """
    Whether the change can only be applied by deleting and creating the client.
    """
    for field in changed:
        if field in RECREATE_FIELDS:
            return True
        if field not in CLEARABLE_FIELDS and not getattr(desired, field):
            return True
    return False
