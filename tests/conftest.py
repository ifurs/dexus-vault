import pytest

from dexus_vault.dex import DexError
from dexus_vault.models import Client
from dexus_vault.sources import SecretEntry


class FakeDex:
    """
    In-memory stand-in for DexAPI that mimics the Dex server semantics.
    """

    def __init__(self, api_version: int = 4, static: tuple[str, ...] = ()):
        self.api_version = api_version
        self.clients: dict[str, Client] = {}
        self.static = set(static)
        self.calls: list[tuple[str, str]] = []
        self.fail: set[tuple[str, str]] = set()

    @property
    def supports_list(self) -> bool:
        return self.api_version >= 3

    @property
    def supports_extended_fields(self) -> bool:
        return self.api_version >= 4

    def _check(self, method: str, client_id: str) -> None:
        self.calls.append((method, client_id))
        if (method, client_id) in self.fail:
            raise DexError(f"{method} {client_id}: injected failure")

    def get_client(self, client_id):
        self._check("get", client_id)
        return self.clients.get(client_id)

    def list_client_ids(self):
        self._check("list", "*")
        return sorted(self.clients.keys() | self.static)

    def create_client(self, client):
        self._check("create", client.id)
        if client.id in self.clients:
            raise DexError("already exists")
        self.clients[client.id] = client

    def update_client(self, client):
        self._check("update", client.id)
        self.clients[client.id] = self.clients[client.id].model_copy(
            update={
                k: getattr(client, k)
                for k in Client.model_fields
                if k not in ("id", "secret", "public")
            }
        )

    def delete_client(self, client_id):
        self._check("delete", client_id)
        if client_id in self.static:
            raise DexError("static clients: read-only cannot delete client")
        return self.clients.pop(client_id, None) is not None

    def mutations(self):
        return [call for call in self.calls if call[0] not in ("get", "list")]


class FakeSource:
    def __init__(self, secrets: dict | None = None):
        self.secrets = secrets or {}
        self.errors: dict[str, str] = {}

    def read_secrets(self):
        entries = [SecretEntry(key, data) for key, data in self.secrets.items()]
        entries += [SecretEntry(key, None, err) for key, err in self.errors.items()]
        return entries


@pytest.fixture
def dex():
    return FakeDex()


@pytest.fixture
def source():
    return FakeSource()
