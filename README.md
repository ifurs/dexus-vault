# DEXUS VAULT

[![Latest Github release](https://img.shields.io/github/tag/ifurs/dexus-vault.svg)](https://github.com/ifurs/dexus-vault/releases/latest)
![Python](https://img.shields.io/badge/python-v3.11+-blue.svg)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

## **dexus-vault** - synchronizer of Dex clients with secrets in Vault or AWS SSM

## 🚩 Table of Contents

- [About the project](#-about-the-project)
  - [How it works](#how-it-works)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
  - [General and sync](#general-and-sync)
  - [Metrics and health](#metrics-and-health)
  - [Dex connection](#dex-connection)
  - [Vault connection](#vault-connection)
  - [AWS SSM Parameter Store](#aws-ssm-parameter-store)
- [Vault secret structure](#-vault-secret-structure)
- [Pruning](#-pruning)
- [Metrics](#-metrics)
- [Running in Kubernetes](#-running-in-kubernetes)
- [Local testing](#-local-testing)
- [Development](#-development)
- [Upgrading from 0.3](#-upgrading-from-03)
- [Thanks](#-thanks)

## 🚀 About the project

Dexus Vault keeps the OAuth2 clients of [Dex](https://dexidp.io) in sync with secrets stored in HashiCorp Vault or in AWS Systems Manager Parameter Store.
The secret backend is the source of truth: every secret under a path describes one Dex client.

### How it works

Every `SYNC_INTERVAL` seconds dexus-vault:

1. lists and reads the secrets under `VAULT_MOUNT_POINT`/`VAULT_CLIENTS_PATH` (or the parameters under `SSM_PATH`), and validates each one as a client;
2. fetches each client from Dex over gRPC and compares them;
3. applies the difference:
   - missing clients are **created**;
   - changed clients are **updated in place** with `UpdateClient`;
   - clients are **recreated** (deleted and created again) only when Dex cannot update the change in place: a new `secret`, a change of `public`, or clearing a list/name/logo;
   - with [pruning](#-pruning) enabled, clients that are no longer in the backend are **deleted**.

Secrets that are invalid, or that define the same client id twice, are reported and their clients are left untouched.

## 💾 Installation

```bash
pip install dexus-vault          # Vault backend
pip install 'dexus-vault[aws]'   # adds the AWS SSM backend (boto3)
```

or with Docker:

```bash
docker run --env-file .env ifurs/dexus-vault
```

The image includes both backends. See the [image README](docker/image/README.md).

## 📙 Usage

```bash
dexus-vault                # sync continuously
dexus-vault --once         # one sync, exit code 1 if anything failed
dexus-vault --dry-run      # log what would change, change nothing
dexus-vault --prune        # also delete clients that are not in Vault
python3 -m dexus_vault     # same as dexus-vault
```

All options:

```text
--once                    run one sync and exit, non-zero on errors (SYNC_ONCE)
--dry-run                 log changes without applying them (SYNC_DRY_RUN)
--prune, --no-prune       delete Dex clients missing in the source (SYNC_PRUNE)
--backend {vault,aws-ssm} where clients are read from (SECRETS_BACKEND)
--interval INTERVAL       seconds between syncs (SYNC_INTERVAL)
--log-level LOG_LEVEL     log level (LOG_LEVEL)
--log-format {text,json}  log format (LOG_FORMAT)
--env-file ENV_FILE       dotenv file to read (default: .env)
```

Exit codes: `0` success or clean shutdown (SIGTERM/SIGINT), `1` Dex or Vault unreachable or a failed `--once` sync, `2` invalid configuration.

## 🔧 Configuration

Settings are read from environment variables and from a `.env` file in the working directory (or `--env-file`). Command line flags win over both.

### General and sync

| variable | default | description |
|:---|:---:|:---|
| SECRETS_BACKEND | vault | `vault` or `aws-ssm` |
| SYNC_INTERVAL | 60 | Seconds between syncs |
| SYNC_ONCE | false | Run one sync and exit |
| SYNC_DRY_RUN | false | Log planned changes without applying them |
| SYNC_PRUNE | false | Delete Dex clients that are not defined in the backend, see [Pruning](#-pruning) |
| SYNC_PRUNE_PREFIX | - | Only prune clients whose id starts with this prefix |
| SYNC_PRUNE_EXCLUDE | - | Comma-separated client ids that are never pruned |
| LOG_LEVEL | INFO | DEBUG, INFO, WARNING, ERROR or CRITICAL |
| LOG_FORMAT | text | `text` or `json` (one JSON object per line) |

### Metrics and health

| variable | default | description |
|:---|:---:|:---|
| METRICS_ENABLE | true | Serve `/metrics`, `/healthz` and `/readyz` (not in `--once` mode) |
| METRICS_ADDR | 0.0.0.0 | Listen address |
| METRICS_PORT | 8000 | Listen port |
| INTERNAL_METRICS | false | Also export Python process, platform and GC metrics |

### Dex connection

| variable | default | description |
|:---|:---:|:---|
| DEX_GRPC_URL | 127.0.0.1:5557 | Dex gRPC address |
| DEX_CA_CRT | - | CA that signed the Dex gRPC server certificate (enables TLS) |
| DEX_CLIENT_CRT | - | Client certificate for mutual TLS |
| DEX_CLIENT_KEY | - | Client certificate key for mutual TLS |
| DEX_TIMEOUT | 10 | Deadline in seconds for each gRPC call |
| DEX_MAX_RETRIES | 20 | Startup retries while Dex is unreachable |
| DEX_RETRY_WAIT | 3 | Seconds between startup retries |

`CA_CRT`, `CLIENT_CRT` and `CLIENT_KEY` are still accepted as aliases.

Without any certificate the connection is **not encrypted** and a warning is logged. Dex's gRPC API gives full administrative access, so configure `grpc.tlsClientCA` in Dex and use mutual TLS. Setting only `DEX_CA_CRT` gives server-authenticated TLS; without it the system CA store is used to verify Dex.

Dex version notes: dexus-vault works with any Dex v2 release, but `allowed_connectors`, `sso_shared_with`, `backchannel_logout_uri`, `post_logout_redirect_uris` and `refresh_token_lifetime` need **Dex v2.46.0** (they are ignored, with a warning, on older servers), and pruning needs **Dex v2.44.0** (`ListClients`).

### Vault connection

| variable | required | default | description |
|:---|:---:|:---:|:---|
| VAULT_ADDR | - | http://127.0.0.1:8200 | Vault address |
| VAULT_MOUNT_POINT | yes | - | KV engine [mount point](https://developer.hashicorp.com/vault/docs/secrets/kv) |
| VAULT_CLIENTS_PATH | yes | - | Path inside the engine that holds one secret per client |
| VAULT_ENGINE | - | v2 | KV engine version, `v1` or `v2` |
| VAULT_NAMESPACE | - | - | Vault Enterprise / HCP namespace |
| VAULT_CERT_CA | - | true | TLS verification: `true` (system CA store), `false`, or a path to a CA bundle |
| VAULT_REQUEST_TIMEOUT | - | 10 | Seconds per Vault request |
| VAULT_ALLOW_REDIRECT | - | false | Follow HTTP redirects |
| VAULT_PROXIES | - | - | JSON, e.g. `{"https": "http://proxy:3128"}` |
| VAULT_MAX_RETRIES | - | 20 | Startup retries while Vault is unreachable or sealed |
| VAULT_RETRY_WAIT | - | 3 | Seconds between startup retries |
| VAULT_AUTH_METHOD | - | auto | `auto`, `token`, `approle`, `kubernetes`, `ldap` or `cert` |

#### Vault auth

With `VAULT_AUTH_METHOD=auto` the first configured method in this order is used: AppRole, Kubernetes, LDAP, certificate, token.

| method | variables |
|:---|:---|
| Token | `VAULT_TOKEN` |
| AppRole | `VAULT_APPROLE_ROLE_ID` and either `VAULT_APPROLE_SECRET_ID` or `VAULT_APPROLE_SECRET_PATH` (file with the secret id, e.g. written by Vault Agent); `VAULT_APPROLE_MOUNT_POINT` (default `approle`) |
| Kubernetes | `VAULT_KUBERNETES_ROLE`; `VAULT_KUBERNETES_JWT_PATH` (default `/var/run/secrets/kubernetes.io/serviceaccount/token`); `VAULT_KUBERNETES_MOUNT_POINT` (default `kubernetes`) |
| LDAP | `VAULT_LDAP_USERNAME`, `VAULT_LDAP_PASSWORD`; `VAULT_LDAP_MOUNT_POINT` (default `ldap`) |
| Certificate | `VAULT_CERT`, `VAULT_CERT_KEY`; `VAULT_CERT_ROLE` (optional role name); `VAULT_CERT_MOUNT_POINT` (default `cert`). Requires TLS verification |

Tokens obtained by logging in (all methods except token) are renewed before they expire, replaced by a new login when renewal is not possible, and revoked on shutdown.

#### Vault policy

```hcl
# KV v2 mounted at "kv", clients under "dex/"
path "kv/metadata/dex/*" {
  capabilities = ["list"]
}

path "kv/data/dex/*" {
  capabilities = ["read"]
}
```

For KV v1 grant `list` and `read` on `kv/dex/*`.

### AWS SSM Parameter Store

Set `SECRETS_BACKEND=aws-ssm` (or `--backend aws-ssm`) and install the `aws` extra. Every parameter **directly** under `SSM_PATH` is one client; its value is the same JSON object as a [Vault secret](#-vault-secret-structure), and the parameter name below the path is the default client id. Use `SecureString` parameters, they are decrypted on read.

| variable | required | default | description |
|:---|:---:|:---:|:---|
| SSM_PATH | yes | - | Parameter path, e.g. `/dex/clients` |
| AWS_REGION | - | from the AWS config | Region of the parameters |
| AWS_PROFILE | - | - | Shared config / SSO profile |
| SSM_ENDPOINT_URL | - | - | Custom endpoint, e.g. a VPC endpoint or a local emulator |
| SSM_TIMEOUT | - | 10 | Connect and read timeout in seconds |
| SSM_MAX_RETRIES | - | 5 | Attempts per request, throttling is retried |
| AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN | - | - | Static credentials, normally not needed |

Credentials come from the standard AWS chain: environment variables, shared config and SSO profiles, web identity (EKS IRSA), EKS Pod Identity, or the ECS/EC2 instance role. The explicit `AWS_*` key settings exist so credentials can also come from a `.env` file.

```bash
aws ssm put-parameter --type SecureString --name /dex/clients/my-app \
  --value '{"secret": "a-long-random-secret", "redirect_uris": ["https://app.example.com/callback"]}'
```

Minimal IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:GetParametersByPath",
      "Resource": "arn:aws:ssm:eu-west-1:123456789012:parameter/dex/clients"
    }
  ]
}
```

The default `aws/ssm` KMS key lets every principal in the account decrypt. With a customer managed key, also allow `kms:Decrypt` on that key. Parameters whose value is not a JSON object are reported, and pruning is skipped until they are fixed. Nested parameters (`/dex/clients/team/app`) are ignored.

## 🔒 Vault secret structure

Each secret under `VAULT_CLIENTS_PATH` (or parameter under `SSM_PATH`) is one client. All fields of the Dex client API are supported:

```json
{
  "id": "my-first-client",
  "secret": "a-long-random-secret",
  "name": "My First Client",
  "logo_url": "https://example.com/logo.png",
  "public": false,
  "redirect_uris": ["https://app.example.com/callback"],
  "trusted_peers": ["my-second-client"],
  "allowed_connectors": ["github"],
  "sso_shared_with": ["my-second-client"],
  "backchannel_logout_uri": "https://app.example.com/backchannel-logout",
  "post_logout_redirect_uris": ["https://app.example.com/"],
  "refresh_token_lifetime": "standalone"
}
```

- `id` defaults to the secret name.
- `secret` is required for confidential clients. Public clients (`"public": true`) may leave it out, Dex then keeps managing it.
- `refresh_token_lifetime` is `standalone` (default) or `session`.
- Lists can be native JSON lists, JSON-encoded strings (`"[\"a\", \"b\"]"`) or comma-separated strings (`"a,b"`), so they work with the key/value view of the Vault UI too. The same goes for `"public": "true"`.
- camelCase keys (`redirectUris`) are accepted. Unknown keys are ignored with a warning, which catches typos such as `redirect_uri`.
- Sub-paths (folders) under `VAULT_CLIENTS_PATH` are skipped. Soft-deleted KV v2 secrets count as removed.

## ✂️ Pruning

With `SYNC_PRUNE=true` (or `--prune`) clients that exist in Dex but not in the backend are deleted. Dex clients carry no owner label, so limit the scope:

- `SYNC_PRUNE_PREFIX=vault-` only touches clients whose id starts with `vault-`;
- `SYNC_PRUNE_EXCLUDE=admin-ui,cli` never touches the listed ids.

Safety rules, a sync never prunes when:

- some secret could not be read or some client could not be checked in Dex, since the picture is incomplete;
- the backend returned no clients at all (for example a wrong `VAULT_CLIENTS_PATH` or `SSM_PATH`);
- the client belongs to an invalid or duplicated secret.

Static clients from the Dex config file cannot be deleted through the API; the first attempt is logged and they are skipped afterwards. Try `--dry-run --prune --once` first to see what would be deleted.

## 📈 Metrics

Served at `http://<METRICS_ADDR>:<METRICS_PORT>/metrics`:

| metric | type | description |
|:---|:---|:---|
| `dexus_vault_client_operations_total{operation, status}` | counter | `operation`: create, update, recreate, delete; `status`: ok, failed, planned (dry-run) |
| `dexus_vault_syncs_total{result}` | counter | Sync runs, `result`: success or failure |
| `dexus_vault_sync_duration_seconds` | histogram | Duration of a sync run |
| `dexus_vault_last_sync_timestamp_seconds` | gauge | Time of the last sync run |
| `dexus_vault_last_success_timestamp_seconds` | gauge | Time of the last sync without errors |
| `dexus_vault_clients` | gauge | Valid clients defined in the backend |
| `dexus_vault_invalid_secrets` | gauge | Secrets that are not valid client definitions |
| `dexus_vault_build_info{version, backend}` | gauge | Build information and the active backend |

Example alert: `time() - dexus_vault_last_success_timestamp_seconds > 600`.

Health endpoints on the same port:

- `/healthz`: 200 while the process runs (liveness);
- `/readyz`: 200 once a sync succeeded and successes keep coming within `3 × SYNC_INTERVAL + 60s`, 503 otherwise (readiness).

## ☸️ Running in Kubernetes

```yaml
containers:
  - name: dexus-vault
    image: ifurs/dexus-vault:0.4.0
    env:
      - { name: DEX_GRPC_URL, value: "dex.dex.svc:5557" }
      - { name: VAULT_ADDR, value: "https://vault.vault.svc:8200" }
      - { name: VAULT_MOUNT_POINT, value: "kv" }
      - { name: VAULT_CLIENTS_PATH, value: "dex" }
      - { name: VAULT_KUBERNETES_ROLE, value: "dexus-vault" }
      - { name: LOG_FORMAT, value: "json" }
    ports:
      - { name: http, containerPort: 8000 }
    livenessProbe:
      httpGet: { path: /healthz, port: http }
    readinessProbe:
      httpGet: { path: /readyz, port: http }
    securityContext:
      runAsNonRoot: true
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
```

For a CronJob, add `args: ["--once"]`, the pod then fails when the sync fails.

On EKS with the SSM backend, replace the Vault variables with `SECRETS_BACKEND=aws-ssm`, `SSM_PATH` and `AWS_REGION`, and give the service account an IAM role (IRSA or Pod Identity) with the policy above.

## 💻 Local testing

[docker/tests](docker/tests/README.md) has a Docker Compose stack with Dex, a Vault dev server and an AWS SSM emulator ([moto](https://github.com/getmoto/moto)), sample clients and a restricted Vault policy:

```bash
docker/tests/start.sh up
dexus-vault --env-file docker/tests/.env       # Vault
dexus-vault --env-file docker/tests/.env.ssm   # AWS SSM
docker/tests/start.sh down
```

It is not suitable for production.

## 🛠 Development

```bash
pip install -r requirements-dev.txt -e ".[aws]"
pytest                                  # unit tests
docker/tests/start.sh up && DEXUS_INTEGRATION=1 pytest tests/integration
black . && ruff check .
```

The project uses [pre-commit](https://pre-commit.com/).

For [Claude Code](https://claude.com/claude-code), [CLAUDE.md](CLAUDE.md) describes the architecture and invariants, and [.claude/agents](.claude/agents) defines three project agents:

| agent | role |
|:---|:---|
| `dexus-researcher` | read-only; verifies upstream Dex, Vault/hvac, AWS and dependency behavior against tagged sources, keeps verified facts in project memory |
| `dexus-developer` | implements changes along the existing seams, with tests, lint and docs |
| `dexus-tester` | runs unit and integration suites on the local stack, reproduces bugs as failing tests, edits only tests |

The Dex gRPC stubs in `dexus_vault/grpc_dexidp` are generated from [api.proto](https://github.com/dexidp/dex/blob/v2.46.0/api/v2/api.proto). To update them to another Dex release:

```bash
scripts/generate_proto.sh v2.46.0
```

## ⬆️ Upgrading from 0.3

- Python 3.11 or newer is required.
- `VAULT_MOUNT_POINT` and `VAULT_CLIENTS_PATH` are now validated as required, as documented before.
- Metrics were renamed and are now counters with a `dexus_vault_` prefix, see [Metrics](#-metrics). The old `client_create`, `client_delete`, `client_update`, `client_skip` and `incorrect_secrets` gauges are gone.
- Confidential clients with an empty `secret` are rejected. Before, Dex replaced the empty secret with a random one, and dexus-vault recreated the client on every sync.
- Vault TLS is verified by default for every auth method (`VAULT_CERT_CA=true`). Set `VAULT_CERT_CA=false` to turn it off, or point it at your CA bundle.
- Changes are applied in place with `UpdateClient` where possible, so clients are no longer deleted and recreated for every change.
- The Docker image runs as an unprivileged user (uid 65532).

## Roadmap

- [x] Redesign metrics concept to make it more Prometheus friendly
- [x] Switch to pydantic
- [x] Track clients in Dex and prune the ones removed from Vault
- [x] CLI with parameters
- [x] Structured (JSON) logs
- [ ] Generate missing client secrets and write them back to Vault
- [ ] Read clients from several Vault paths, recursively
- [x] AWS SSM Parameter Store backend
- [ ] AWS Secrets Manager and other secret backends

## 🔥 Thanks

- [Hurlenko](https://github.com/hurlenko) for references copied from your repos
