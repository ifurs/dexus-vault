"""
Secret sources: the backends Dex client definitions are read from.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class SourceError(Exception):
    """
    The source cannot be read, a sync must not act on partial data.
    """


@dataclass
class SecretEntry:
    """
    One client definition in a source. `data` is None when the secret is
    deleted (e.g. KV v2 soft delete) or could not be read, in which case
    `error` is set.
    """

    key: str
    data: dict[str, Any] | None
    error: str | None = None


class SecretSource(Protocol):
    name: str

    def connect(self) -> None:
        """Connect and authenticate, raises SourceError."""

    def ensure_session(self, min_ttl: int = 0) -> None:
        """Keep credentials valid for at least `min_ttl` seconds."""

    def read_secrets(self) -> list[SecretEntry]:
        """All client definitions, raises SourceError if they cannot be listed."""

    def close(self) -> None:
        """Release connections and credentials."""
