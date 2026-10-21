# dexus-vault

Daemon that syncs Dex OAuth2 clients over Dex's gRPC API from a secret backend (Vault KV or AWS SSM Parameter Store). The backend is the source of truth.

## Commands

```bash
uv sync --extra aws                           # venv with dev tools from uv.lock
uv run black . && uv run ruff check .         # CI enforces both
uv run pytest -q                              # unit tests, no network
docker/tests/start.sh up                      # Dex :5557, Vault :8200 (token root), SSM emulator :5050
DEXUS_INTEGRATION=1 uv run pytest -q tests/integration
docker/tests/start.sh down
```

## Rules

- IMPORTANT: never log, print or put in exceptions a secret value. Client secrets are `SecretStr`; pydantic errors are rendered with `include_input=False`. Tests assert this.
- `dexus_vault/grpc_dexidp/` is generated. Never edit it, run `scripts/generate_proto.sh <dex-tag>`.
- Dex RPC behavior is not what the proto suggests (empty values in `UpdateClient`, random secrets on create, `UNKNOWN` for not found). Read the `dex-api` skill before touching `dex.py`, `models.py`, `sync.py` or `FakeDex`.
- `Syncer.plan` decides, `_apply` executes; dry-run must never reach a mutating Dex call.
- Pruning stays conservative: no prune on partial or empty source data, never for ids of invalid or duplicate secrets.
- Sources raise `SourceError` only when they cannot list; a bad single secret is a `SecretEntry(error=...)`.
- Configuration is backward compatible: existing env var names keep working (`AliasChoices` in `config.py`); every new setting gets a README table row.
- boto3 is optional: import it only in `dexus_vault/sources/aws_ssm.py`.
- Dependencies are managed with uv: change `pyproject.toml`, run `uv lock`, commit `uv.lock`. Never use pip in this repo.
- Workflows pin actions to full commit SHAs with a version comment, use least-privilege `permissions`, `persist-credentials: false`, and pass `${{ }}` values to `run:` only through `env:`. `uvx zizmor@1.31.1 .github` must stay clean.
- `tests/conftest.py::FakeDex` must behave like real Dex; fix it first when Dex is found to behave differently.
- Every behavior change ships with a test; source, Dex or CLI-loop changes also with an integration test.
- Do not commit, push or open PRs unless asked.

## Agents and skills

`.claude/agents/`: `dexus-researcher` (upstream facts), `dexus-developer` (changes), `dexus-tester` (tests), `dexus-reviewer` (independent review of a diff). Skills in `.claude/skills/`: `dex-api` (Dex semantics reference), `dexus-verify` (the verification gate), `/upgrade-dex-api <tag>` (Dex API upgrade workflow). Agent guard hooks live in `scripts/agents/guard.py`.
