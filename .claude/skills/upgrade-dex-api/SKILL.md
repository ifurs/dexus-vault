---
name: upgrade-dex-api
description: Upgrade the vendored Dex gRPC API to a new Dex release and adapt dexus-vault to it.
disable-model-invocation: true
argument-hint: <dex-tag, e.g. v2.47.0>
---

# Upgrade the Dex API to $ARGUMENTS

1. **Research first.** Ask the dexus-researcher agent to diff `api/v2/api.proto` and `server/apiserver/clients.go` between the currently vendored tag (see the `dex-api` skill and README) and `$ARGUMENTS`, and to report: new or changed `Client`/`UpdateClientReq` fields, presence (`optional`) changes, new RPCs, changed error behavior, and the new `GetVersion().api` number.
2. **Regenerate the stubs**: `scripts/generate_proto.sh $ARGUMENTS`, then `uv run black dexus_vault/grpc_dexidp`. Do not hand-edit generated files.
3. **Adapt the code** with the dexus-developer agent, based on the research:
   - new client fields → `models.Client`, `from_proto`, `to_proto`, `to_update_request`; add them to `EXTENDED_FIELDS` with a new API version gate if older servers lack them; to `CLEARABLE_FIELDS` if `UpdateClient` can clear them;
   - new API version → constants in `dex.py` and the capability properties;
   - `tests/conftest.py::FakeDex` updated to the new semantics first.
4. **Update docs**: the `dex-api` skill tables (and its "verified against" tag), README secret structure and Dex version notes, the `api.proto` link in the README.
5. **Bump the test stack**: `dexidp/dex` image tag in `docker/tests/docker-compose.yaml`.
6. **Verify** with the `dexus-verify` skill, including integration tests against the new Dex image, and have the dexus-reviewer agent review the diff.
