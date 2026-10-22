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
  - [EKS with the AWS SSM backend](#eks-with-the-aws-ssm-backend)
- [Local testing](#-local-testing)
- [Development](#-development)
- [Releasing](#-releasing)
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
uv tool install dexus-vault          # Vault backend
uv tool install 'dexus-vault[aws]'   # adds the AWS SSM backend (boto3)
```

`pip install dexus-vault` works as well.

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

### EKS with the AWS SSM backend

No AWS keys are needed in the pod. Give its service account an IAM role with the [SSM policy](#aws-ssm-parameter-store), using either IRSA or EKS Pod Identity. boto3 picks up both automatically and refreshes the temporary credentials itself, including the rotated IRSA token.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: dexus-vault
  namespace: dex
  annotations:
    # IRSA only; with Pod Identity leave this out and create an association instead
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/dexus-vault
---
# in the Deployment's pod spec
serviceAccountName: dexus-vault
containers:
  - name: dexus-vault
    image: ifurs/dexus-vault:0.4.0
    env:
      - { name: SECRETS_BACKEND, value: "aws-ssm" }
      - { name: SSM_PATH, value: "/dex/clients" }
      - { name: AWS_REGION, value: "eu-west-1" }
      - { name: DEX_GRPC_URL, value: "dex.dex.svc:5557" }
    # ports, probes and securityContext as above
```

**IRSA:** the role's trust policy allows the cluster's OIDC provider for this service account:

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:dex:dexus-vault",
      "oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE:aud": "sts.amazonaws.com"
    }
  }
}
```

**Pod Identity:** install the `eks-pod-identity-agent` add-on. Trust `pods.eks.amazonaws.com` with `sts:AssumeRole` and `sts:TagSession`, then associate the role:

```bash
aws eks create-pod-identity-association --cluster-name my-cluster \
  --namespace dex --service-account dexus-vault \
  --role-arn arn:aws:iam::123456789012:role/dexus-vault
```

Things that commonly go wrong:

- **Static keys win.** `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in the pod environment take precedence over IRSA and Pod Identity, so leave them unset.
- **Private clusters** need VPC interface endpoints: `ssm`, plus `sts` for IRSA or `eks-auth` for Pod Identity. If you use a custom SSM endpoint, set `SSM_ENDPOINT_URL`; `AWS_ENDPOINT_URL_STS` works for STS.
- **Don't rely on the node role.** IMDSv2 with the default hop limit of 1 usually blocks pods from reaching it, so the sync fails with "Unable to locate credentials".
- **Customer managed KMS keys** need `kms:Decrypt` for the role.

The image works with `runAsNonRoot` and `readOnlyRootFilesystem`. Both credential paths were checked that way by hand, against an emulated STS and Pod Identity agent; the integration tests cover IRSA.

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

The project is managed with [uv](https://docs.astral.sh/uv/). Dependencies are pinned in `uv.lock`.

```bash
uv sync --extra aws                     # .venv with the locked runtime and dev dependencies
uv run pytest                           # unit tests
docker/tests/start.sh up && DEXUS_INTEGRATION=1 uv run pytest tests/integration
uv run black . && uv run ruff check .
uv lock --upgrade                       # update dependencies, then commit uv.lock
```

The project uses [pre-commit](https://pre-commit.com/); the hooks also keep `uv.lock` in sync with `pyproject.toml`.

Security checks, all of which also run in CI:

```bash
uv audit --preview-features audit-command --frozen   # known vulnerabilities in locked dependencies
uvx zizmor@1.31.1 .github                            # GitHub Actions security
uvx bandit@1.9.2 -q -r dexus_vault scripts -x dexus_vault/grpc_dexidp
```

CI also scans the Docker image with Trivy and fails on fixable HIGH or CRITICAL vulnerabilities. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

For [Claude Code](https://claude.com/claude-code), [CLAUDE.md](CLAUDE.md) holds the project rules, and `.claude/` defines project agents and skills:

| agent | model | role |
|:---|:---|:---|
| `dexus-researcher` | opus | read-only; verifies upstream Dex, Vault/hvac, AWS and dependency behavior against tagged sources, keeps verified facts in project memory |
| `dexus-developer` | opus | implements changes test-first along the existing seams; a Stop hook blocks it from finishing while lint or unit tests fail |
| `dexus-tester` | sonnet | runs unit and integration suites against local endpoints only, reproduces bugs as failing tests; may edit test code only |
| `dexus-reviewer` | opus | independent review of a diff in a fresh context, re-runs the checks, reports only correctness, security and requirement gaps |
| `dexus-security-auditor` | opus | read-only security audit: runs the scanner suite, checks the threat model, reports only high-confidence exploitable findings; keeps accepted risks in project memory |

| skill | use |
|:---|:---|
| `dex-api` | verified Dex RPC semantics and version matrix, preloaded into the agents |
| `dexus-verify` | the verification gate: which checks to run for which change, and how to report evidence |
| `/upgrade-dex-api <tag>` | step-by-step upgrade of the vendored Dex API |
| `/security-audit [full \| diff <base>]` | the security audit procedure: scanners, threat model, how findings are judged |

The hooks used by the agents are in [scripts/agents/guard.py](scripts/agents/guard.py), tested in `tests/test_agent_guard.py`.

The Dex gRPC stubs in `dexus_vault/grpc_dexidp` are generated from [api.proto](https://github.com/dexidp/dex/blob/v2.46.0/api/v2/api.proto). To update them to another Dex release:

```bash
scripts/generate_proto.sh v2.46.0
```

## 🚢 Releasing

Releases are automatic and never start from a hand-pushed tag:

1. Open a pull request that bumps `__version__` in `dexus_vault/__version__.py` (`MAJOR.MINOR.PATCH`). CI's *Release preview* check shows "Merging this pull request releases X" and fails if the version is lower than the latest release.
2. Review and merge it into `main`.
3. The *Release* workflow (`.github/workflows/publish-to-pypi.yml`) sees a version without a tag, then builds with `uv build`, publishes to PyPI with trusted publishing, creates the tag and a GitHub release with Sigstore-signed files and generated notes, and publishes the signed multi-arch Docker image.

Pushing tags by hand does not release anything, and the *Release* workflow cannot be started by hand: it only runs for commits on `main`. If a release job fails, re-run the failed jobs. They reuse the same build, so PyPI and the GitHub release always carry identical files, and the PyPI upload skips files that are already there. Builds set `SOURCE_DATE_EPOCH` to the commit time, which makes the wheel reproducible (the sdist still records file modification times).

To publish the Docker image of an existing release again, run *Publish Docker image* manually from `main` with the tag. It refuses tags that do not point to a commit on `main` whose `__version__` matches, and builds that exact commit; the image label `org.opencontainers.image.revision` and the cosign signature annotations record it.

The workflows only release from `main`, but the repository settings decide who can change `main` and tags. Configure them (Settings → Rules / Environments):

- **A branch ruleset on `main`** requiring pull requests, an approving review and passing CI, with no bypass. Without it, a direct push to `main` releases without review.
- **A tag ruleset on `*.*.*`** that blocks updates and deletions (creation stays allowed for the release workflow), plus **immutable releases**, so a published version and its tag cannot be changed.
- **The `pypi` and `dockerhub` environments**: deployment branches limited to `main`, required reviewers, and administrators not allowed to bypass, so every release waits for a maintainer's approval.
- On PyPI, the trusted publisher limited to the `pypi` environment.

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
