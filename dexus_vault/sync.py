"""
Synchronization logic: read the desired clients from the source, compare them
with Dex, then create, update, recreate or prune clients.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import ValidationError

from dexus_vault.dex import DexError
from dexus_vault.log import logger
from dexus_vault.models import Client, changed_fields, needs_recreate
from dexus_vault.sources import SecretEntry, SecretSource

Operation = Literal["create", "update", "recreate", "delete"]


class DexBackend(Protocol):
    supports_list: bool
    supports_extended_fields: bool

    def get_client(self, client_id: str) -> Client | None: ...
    def list_client_ids(self) -> list[str]: ...
    def create_client(self, client: Client) -> None: ...
    def update_client(self, client: Client) -> None: ...
    def delete_client(self, client_id: str) -> bool: ...


@dataclass
class SyncOptions:
    dry_run: bool = False
    prune: bool = False
    prune_prefix: str = ""
    prune_exclude: list[str] = field(default_factory=list)


@dataclass
class Action:
    operation: Operation
    client_id: str
    client: Client | None = None
    fields: list[str] = field(default_factory=list)

    def describe(self) -> str:
        text = f"{self.operation} client '{self.client_id}'"
        if self.fields:
            text += f" (changed: {', '.join(self.fields)})"
        return text


@dataclass
class DesiredState:
    clients: dict[str, Client] = field(default_factory=dict)
    # ids that must never be pruned: invalid, duplicated or unreadable secrets
    protected: set[str] = field(default_factory=set)
    invalid: int = 0
    # False when some secret could not be read, the state is then partial
    complete: bool = True


@dataclass
class SyncReport:
    clients: int = 0
    unchanged: int = 0
    invalid: int = 0
    errors: int = 0
    # (operation, status) -> count, status is ok, failed or planned
    operations: dict[tuple[str, str], int] = field(
        default_factory=lambda: defaultdict(int)
    )

    @property
    def ok(self) -> bool:
        return self.errors == 0


def _validation_summary(error: ValidationError) -> str:
    # never include input values, they may contain the client secret
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'secret'}: "
        f"{item['msg'].removeprefix('Value error, ')}"
        for item in error.errors(include_input=False, include_url=False)
    )


def collect_desired(
    entries: list[SecretEntry], warn: Callable[[str], None] = logger.warning
) -> DesiredState:
    """
    Validate secrets and drop duplicated client ids.
    """
    state = DesiredState()
    keys_by_id: dict[str, list[str]] = defaultdict(list)
    known_keys = Client.known_keys()

    for entry in entries:
        if entry.error is not None:
            logger.error(f"Cannot read secret '{entry.key}': {entry.error}")
            state.complete = False
            state.protected.add(entry.key)
            continue
        if entry.data is None:
            logger.debug(f"Secret '{entry.key}' is deleted, skipping")
            continue

        data = dict(entry.data)
        if not data.get("id"):
            data["id"] = entry.key
        client_id = str(data["id"])
        unknown = sorted(set(data) - known_keys)
        if unknown:
            warn(
                f"Secret '{entry.key}' has unknown fields, ignored: {', '.join(unknown)}"
            )
        try:
            client = Client.model_validate(data)
        except ValidationError as error:
            warn(
                f"Secret '{entry.key}' is not a valid client: {_validation_summary(error)}"
            )
            state.invalid += 1
            state.protected.add(client_id)
            continue
        keys_by_id[client.id].append(entry.key)
        state.clients[client.id] = client

    for client_id, keys in keys_by_id.items():
        if len(keys) > 1:
            logger.error(
                f"Client id '{client_id}' is defined by several secrets "
                f"({', '.join(keys)}), leaving it untouched until fixed"
            )
            del state.clients[client_id]
            state.protected.add(client_id)
            state.invalid += len(keys)
    return state


def plan_client(
    desired: Client, actual: Client | None, extended: bool = True
) -> Action | None:
    if actual is None:
        return Action("create", desired.id, desired)
    changed = changed_fields(desired, actual, extended=extended)
    if not changed:
        return None
    operation = "recreate" if needs_recreate(desired, changed) else "update"
    return Action(operation, desired.id, desired, changed)


class Syncer:
    def __init__(
        self,
        dex: DexBackend,
        source: SecretSource,
        options: SyncOptions | None = None,
    ):
        self.dex = dex
        self.source = source
        self.options = options or SyncOptions()
        # clients Dex refused to delete (e.g. static clients from its config)
        self._unprunable: set[str] = set()
        self._warned: set[str] = set()

    def _warn_once(self, message: str) -> None:
        """
        Warn about a problem the first time, it repeats on every sync.
        """
        if message in self._warned:
            logger.debug(message)
        else:
            self._warned.add(message)
            logger.warning(message)

    def _warn_unsupported_fields(self, client: Client) -> None:
        fields = client.uses_extended_fields()
        if fields and not self.dex.supports_extended_fields:
            self._warn_once(
                f"Client '{client.id}' sets {', '.join(fields)}, "
                "which need Dex v2.46.0 or newer, ignored"
            )

    def plan(self, state: DesiredState, report: SyncReport) -> list[Action]:
        actions = []
        for client in state.clients.values():
            self._warn_unsupported_fields(client)
            try:
                actual = self.dex.get_client(client.id)
            except DexError as error:
                logger.error(f"Cannot check client '{client.id}' in Dex: {error}")
                report.errors += 1
                state.complete = False
                continue
            action = plan_client(
                client, actual, extended=self.dex.supports_extended_fields
            )
            if action is None:
                logger.debug(f"Client '{client.id}' is up to date")
                report.unchanged += 1
            else:
                actions.append(action)
        if self.options.prune:
            actions.extend(self._plan_prune(state, report))
        return actions

    def _plan_prune(self, state: DesiredState, report: SyncReport) -> list[Action]:
        if not self.dex.supports_list:
            return []
        if not state.complete:
            logger.warning("Skipping prune, some clients could not be read or checked")
            return []
        if not state.clients and not state.protected:
            logger.warning("Skipping prune, no clients found in the source")
            return []
        try:
            existing = self.dex.list_client_ids()
        except DexError as error:
            logger.error(f"Skipping prune: {error}")
            report.errors += 1
            return []
        keep = state.clients.keys() | state.protected | set(self.options.prune_exclude)
        return [
            Action("delete", client_id)
            for client_id in existing
            if client_id not in keep
            and client_id not in self._unprunable
            and client_id.startswith(self.options.prune_prefix)
        ]

    def _apply(self, action: Action) -> None:
        if action.operation == "create":
            self.dex.create_client(action.client)
        elif action.operation == "update":
            self.dex.update_client(action.client)
        elif action.operation == "recreate":
            self.dex.delete_client(action.client_id)
            try:
                self.dex.create_client(action.client)
            except DexError as error:
                raise DexError(
                    f"client '{action.client_id}' was deleted but could not be "
                    f"created again, will retry next sync: {error}"
                ) from error
        elif action.operation == "delete":
            try:
                self.dex.delete_client(action.client_id)
            except DexError:
                self._unprunable.add(action.client_id)
                raise

    def run_once(self) -> SyncReport:
        report = SyncReport()
        state = collect_desired(self.source.read_secrets(), warn=self._warn_once)
        report.clients = len(state.clients)
        report.invalid = state.invalid

        for action in self.plan(state, report):
            if self.options.dry_run:
                logger.info(f"[dry-run] would {action.describe()}")
                report.operations[(action.operation, "planned")] += 1
                continue
            try:
                self._apply(action)
            except DexError as error:
                logger.error(f"Failed to {action.describe()}: {error}")
                if action.operation == "delete":
                    logger.info(f"Client '{action.client_id}' will not be pruned again")
                report.operations[(action.operation, "failed")] += 1
                report.errors += 1
                continue
            logger.info(f"Done: {action.describe()}")
            report.operations[(action.operation, "ok")] += 1

        logger.info(
            f"Sync finished: {report.clients} clients, {report.unchanged} unchanged, "
            f"{report.invalid} invalid, {report.errors} errors"
        )
        return report
