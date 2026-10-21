# dexus-vault

Daemon that syncs Dex OAuth2 clients (over Dex's gRPC API) from a secret backend: HashiCorp Vault KV or AWS SSM Parameter Store. The backend is the source of truth.

## Layout

| path | role |
|:---|:---|
| `dexus_vault/cli.py` | argparse CLI, signal handling, sync loop, exit codes (0 ok, 1 failure, 2 config) |
| `dexus_vault/config.py` | pydantic-settings classes; env var name = field name; `.env` support |
| `dexus_vault/models.py` | `Client` model, input normalization, `changed_fields`, `needs_recreate` |
| `dexus_vault/sync.py` | `collect_desired` → `Syncer.plan` → apply; pruning; `SyncReport` |
| `dexus_vault/dex.py` | `DexAPI` gRPC wrapper, deadlines, API version capabilities |
| `dexus_vault/sources/` | `SecretSource` protocol + `vault.py`, `aws_ssm.py` backends |
| `dexus_vault/metrics.py` | Prometheus registry and the `/metrics` `/healthz` `/readyz` server |
| `dexus_vault/grpc_dexidp/` | **generated** stubs, never edit by hand: `scripts/generate_proto.sh <dex-tag>` |
| `tests/` | unit tests; `tests/conftest.py` has `FakeDex` / `FakeSource` |
| `tests/integration/` | end-to-end against `docker/tests` stack, needs `DEXUS_INTEGRATION=1` |
| `docker/tests/` | compose stack: Dex v2.46, Vault dev (token `root`), moto SSM emulator |

## Commands

```bash
pip install -r requirements-dev.txt -e ".[aws]"
black . && ruff check .                      # formatting and lint, CI enforces both
pytest                                        # unit tests, fast, no network
docker/tests/start.sh up                      # Dex :5557, Vault :8200, SSM :5050, writes .env/.env.ssm
DEXUS_INTEGRATION=1 pytest tests/integration  # end-to-end
docker/tests/start.sh down
```

## Invariants, do not break

- **Never log or print secret values.** Client secrets are `SecretStr`; validation errors are logged with `include_input=False`; config errors too. Tests assert this.
- **Dex semantics** (verified in dex `server/apiserver/clients.go`, v2.46.0):
  - `GetClient` not found arrives as gRPC `UNKNOWN` with "not found" in details.
  - `CreateClient` replaces an empty secret with a random one for non-public clients, so confidential clients must have a secret.
  - `UpdateClient` cannot change `secret`/`public` and treats empty lists/strings as "leave unchanged", except `backchannel_logout_uri` and `refresh_token_lifetime` (proto3 `optional`). Changes that need those go through delete + create (`needs_recreate`).
  - Static clients from the Dex config appear in `ListClients` but cannot be deleted.
  - API version from `GetVersion`: 2 ≤ v2.43, 3 = v2.44–2.45 (`ListClients`), 4 = v2.46 (extended client fields).
- **Pruning must stay conservative**: skipped when any secret is unreadable, when the source returned nothing, and for ids of invalid/duplicate secrets.
- **Plan/apply separation**: `Syncer.plan` decides, `_apply` executes; dry-run must never call mutating Dex methods.
- **Backward compatible configuration**: existing env var names keep working (see `AliasChoices` in `config.py`). New settings get a README table row.
- **A source raises `SourceError` when it cannot list**; per-secret problems become `SecretEntry(error=...)`, never an exception.
- Python ≥ 3.11. boto3 is optional (`[aws]` extra), import it only inside `sources/aws_ssm.py`.

## Conventions

- Match the existing style: small modules, f-string log messages that name the client/secret, docstrings only where behavior is non-obvious.
- Every behavior change comes with a unit test; backend or Dex interaction changes also with an integration test.
- `FakeDex` must mirror real Dex semantics above; if you learn Dex behaves differently, fix `FakeDex` first.
- Do not commit, push or open PRs unless asked.
