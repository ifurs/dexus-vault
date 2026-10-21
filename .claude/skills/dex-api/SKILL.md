---
name: dex-api
description: Verified behavior of the Dex gRPC client API (GetClient, CreateClient, UpdateClient, DeleteClient, ListClients) and which Dex release supports what. Use before changing dexus_vault/dex.py, models.py, sync.py or tests/conftest.py FakeDex, or when a sync behaves unexpectedly against Dex.
user-invocable: false
---

# Dex client API: verified behavior

Verified against `dexidp/dex` tag **v2.46.0**, `server/apiserver/clients.go` and `storage/static.go`. When Dex is upgraded, re-verify with the dexus-researcher agent and update this file.

## RPC semantics

| RPC | behavior that matters here | dexus-vault handling |
|:---|:---|:---|
| `GetClient` | storage `ErrNotFound` is returned as a plain error, so it arrives as gRPC `UNKNOWN` with "not found" in the details. Other storage failures are also `UNKNOWN`. | `dex._is_not_found` checks code `NOT_FOUND`, or `UNKNOWN` + "not found"; anything else is a `DexError`, never "absent". |
| `CreateClient` | empty `id` → random id; empty `secret` on a non-public client → random secret; `already_exists=true` instead of an error on conflict. | Confidential clients without a secret are rejected in `models.Client`, otherwise every sync would see a different secret and recreate. |
| `UpdateClient` | cannot change `secret` or `public`. Lists and `name` / `logo_url` are only applied when non-empty, so they **cannot be cleared**. `backchannel_logout_uri` and `refresh_token_lifetime` are proto3 `optional`: present + empty clears them. Returns `not_found=true` instead of an error. | `models.needs_recreate` sends those changes through delete + create; `to_update_request` always sets the optional fields. |
| `DeleteClient` | `not_found=true` instead of an error. Static clients (Dex config file) fail with an error. | Prune remembers clients that failed to delete and does not retry them. |
| `ListClients` | returns `ClientInfo` without secrets, **includes static clients**. | Used only for pruning; secrets are compared via `GetClient`. |

`refresh_token_lifetime` accepts `""`, `"standalone"` (default, same as empty) and `"session"`; anything else is rejected by Dex.

## Versions

| Dex release | `GetVersion().api` | adds |
|:---|:---:|:---|
| ≤ v2.43 | 2 | base client fields: id, secret, redirect_uris, trusted_peers, public, name, logo_url |
| v2.44 – v2.45 | 3 | `ListClients` RPC (pruning) |
| v2.46 | 4 | client fields `allowed_connectors`, `sso_shared_with`, `backchannel_logout_uri`, `post_logout_redirect_uris`, `refresh_token_lifetime` (`models.EXTENDED_FIELDS`) |

Older servers ignore unknown fields, so sending extended fields is harmless, but comparing them would update forever: `changed_fields(extended=False)` skips them below API 4.

## Testing against these semantics

`tests/conftest.py::FakeDex` mirrors the table: `update_client` does not touch `secret`/`public`, `delete_client` raises for static ids, `list_client_ids` includes static ids, and `api_version` controls `supports_list` / `supports_extended_fields`. Any new Dex behavior goes into `FakeDex` first, with a test naming it, and into the integration tests against the real Dex in `docker/tests`.
