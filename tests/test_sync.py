from dexus_vault.models import Client
from dexus_vault.sync import Syncer, SyncOptions, collect_desired
from dexus_vault.vault import SecretEntry

from .conftest import FakeDex


def client(id="app", **kwargs):
    return Client.model_validate({"id": id, "secret": "s", **kwargs})


def test_creates_missing_clients(dex, source):
    source.secrets = {"app": {"secret": "s", "name": "App"}}
    report = Syncer(dex, source).run_once()
    assert report.ok
    assert dex.mutations() == [("create", "app")]
    assert dex.clients["app"].name == "App"


def test_id_defaults_to_secret_key(dex, source):
    source.secrets = {
        "from-key": {"secret": "s"},
        "other": {"id": "explicit", "secret": "s"},
    }
    Syncer(dex, source).run_once()
    assert set(dex.clients) == {"from-key", "explicit"}


def test_unchanged_clients_are_left_alone(dex, source):
    dex.clients["app"] = client(name="App")
    source.secrets = {"app": {"secret": "s", "name": "App"}}
    report = Syncer(dex, source).run_once()
    assert dex.mutations() == []
    assert report.unchanged == 1


def test_updates_in_place_when_possible(dex, source):
    dex.clients["app"] = client(redirect_uris=["http://a"])
    source.secrets = {"app": {"secret": "s", "redirect_uris": ["http://a", "http://b"]}}
    report = Syncer(dex, source).run_once()
    assert dex.mutations() == [("update", "app")]
    assert dex.clients["app"].redirect_uris == ["http://a", "http://b"]
    assert report.operations[("update", "ok")] == 1


def test_recreates_when_secret_changes(dex, source):
    dex.clients["app"] = client(secret="old")
    source.secrets = {"app": {"secret": "new"}}
    Syncer(dex, source).run_once()
    assert dex.mutations() == [("delete", "app"), ("create", "app")]
    assert dex.clients["app"].secret.get_secret_value() == "new"


def test_recreates_when_a_list_must_be_cleared(dex, source):
    dex.clients["app"] = client(trusted_peers=["other"])
    source.secrets = {"app": {"secret": "s"}}
    Syncer(dex, source).run_once()
    assert dex.mutations() == [("delete", "app"), ("create", "app")]
    assert dex.clients["app"].trusted_peers == []


def test_failed_recreate_is_reported(dex, source):
    dex.clients["app"] = client(secret="old")
    dex.fail.add(("create", "app"))
    source.secrets = {"app": {"secret": "new"}}
    report = Syncer(dex, source).run_once()
    assert not report.ok
    assert report.operations[("recreate", "failed")] == 1


def test_invalid_secrets_are_counted_and_skipped(dex, source):
    source.secrets = {
        "good": {"secret": "s"},
        "no-secret": {"name": "x"},
        "bad-type": {"secret": "s", "public": "maybe"},
    }
    report = Syncer(dex, source).run_once()
    assert set(dex.clients) == {"good"}
    assert report.invalid == 2
    assert report.ok


def test_validation_errors_do_not_log_secret_values(dex, source, caplog):
    source.secrets = {"app": {"secret": "hunter2", "redirect_uris": 42}}
    Syncer(dex, source).run_once()
    assert "redirect_uris" in caplog.text
    assert "hunter2" not in caplog.text


def test_unknown_fields_are_warned_about(dex, source, caplog):
    source.secrets = {"app": {"secret": "s", "redirect_uri": "typo"}}
    Syncer(dex, source).run_once()
    assert "unknown fields, ignored: redirect_uri" in caplog.text


def test_duplicate_ids_are_not_touched(dex, source):
    dex.clients["dup"] = client("dup", name="current")
    source.secrets = {
        "a": {"id": "dup", "secret": "s", "name": "one"},
        "b": {"id": "dup", "secret": "s", "name": "two"},
    }
    report = Syncer(dex, source).run_once()
    assert dex.mutations() == []
    assert dex.clients["dup"].name == "current"
    assert report.invalid == 2


def test_deleted_secrets_are_ignored():
    state = collect_desired([SecretEntry("gone", None)])
    assert state.clients == {} and state.complete


def test_dry_run_changes_nothing(dex, source):
    dex.clients["old"] = client("old")
    source.secrets = {"new": {"secret": "s"}}
    report = Syncer(dex, source, SyncOptions(dry_run=True, prune=True)).run_once()
    assert dex.mutations() == []
    assert report.operations[("create", "planned")] == 1
    assert report.operations[("delete", "planned")] == 1


def test_dex_errors_are_reported(dex, source):
    dex.fail.add(("get", "app"))
    source.secrets = {"app": {"secret": "s"}}
    report = Syncer(dex, source).run_once()
    assert not report.ok
    assert dex.mutations() == []


# --- extended fields and old Dex versions


def test_extended_fields_are_synced_on_new_dex(dex, source):
    dex.clients["app"] = client()
    source.secrets = {"app": {"secret": "s", "allowed_connectors": ["github"]}}
    Syncer(dex, source).run_once()
    assert dex.clients["app"].allowed_connectors == ["github"]


def test_extended_fields_do_not_loop_on_old_dex(source, caplog):
    dex = FakeDex(api_version=3)
    dex.clients["app"] = client()
    source.secrets = {"app": {"secret": "s", "allowed_connectors": ["github"]}}
    syncer = Syncer(dex, source)
    syncer.run_once()
    syncer.run_once()
    assert dex.mutations() == []
    assert caplog.text.count("need Dex v2.46.0") == 1


# --- pruning


def prune(**kwargs):
    return SyncOptions(prune=True, **kwargs)


def test_prune_is_off_by_default(dex, source):
    dex.clients["orphan"] = client("orphan")
    source.secrets = {"app": {"secret": "s"}}
    Syncer(dex, source).run_once()
    assert "orphan" in dex.clients


def test_prune_deletes_orphans(dex, source):
    dex.clients["orphan"] = client("orphan")
    source.secrets = {"app": {"secret": "s"}}
    Syncer(dex, source, prune()).run_once()
    assert set(dex.clients) == {"app"}


def test_prune_respects_prefix_and_exclude(dex, source):
    for id in ("vault-a", "vault-keep", "manual"):
        dex.clients[id] = client(id)
    source.secrets = {"vault-app": {"secret": "s"}}
    Syncer(
        dex, source, prune(prune_prefix="vault-", prune_exclude=["vault-keep"])
    ).run_once()
    assert set(dex.clients) == {"vault-app", "vault-keep", "manual"}


def test_prune_keeps_clients_with_invalid_secrets(dex, source):
    dex.clients["broken"] = client("broken")
    source.secrets = {"app": {"secret": "s"}, "broken": {"name": "missing secret"}}
    Syncer(dex, source, prune()).run_once()
    assert "broken" in dex.clients


def test_prune_skipped_when_vault_read_is_partial(dex, source):
    dex.clients["orphan"] = client("orphan")
    source.secrets = {"app": {"secret": "s"}}
    source.errors = {"unreadable": "permission denied"}
    Syncer(dex, source, prune()).run_once()
    assert "orphan" in dex.clients


def test_prune_skipped_when_vault_is_empty(dex, source):
    dex.clients["orphan"] = client("orphan")
    Syncer(dex, source, prune()).run_once()
    assert "orphan" in dex.clients


def test_prune_skipped_on_dex_without_list_clients(source):
    dex = FakeDex(api_version=2)
    dex.clients["orphan"] = client("orphan")
    source.secrets = {"app": {"secret": "s"}}
    Syncer(dex, source, prune()).run_once()
    assert "orphan" in dex.clients


def test_static_clients_are_tried_once(source):
    dex = FakeDex(static=("static-app",))
    source.secrets = {"app": {"secret": "s"}}
    syncer = Syncer(dex, source, prune())
    assert not syncer.run_once().ok
    assert syncer.run_once().ok
    assert dex.mutations().count(("delete", "static-app")) == 1


def test_repeated_problems_are_warned_once(dex, source, caplog):
    source.secrets = {"bad": {"name": "no secret"}}
    syncer = Syncer(dex, source)
    syncer.run_once()
    syncer.run_once()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "requires a non-empty 'secret'" in warnings[0].message
    assert "Value error" not in warnings[0].message
