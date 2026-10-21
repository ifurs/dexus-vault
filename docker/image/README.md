# DEXUS VAULT

[![Latest Github release](https://img.shields.io/github/tag/ifurs/dexus-vault.svg)](https://github.com/ifurs/dexus-vault/releases/latest)
![Python](https://img.shields.io/badge/python-v3.11+-blue.svg)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

## **dexus-vault** - synchronizer of Dex clients with secrets in Vault

## Usage

```sh
docker run --env-file .env -p 8000:8000 ifurs/dexus-vault
docker run --env-file .env ifurs/dexus-vault --once --dry-run
```

Example `.env`, for clients stored at `kv/dex/*`:

```sh
DEX_GRPC_URL=dex:5557
VAULT_ADDR=https://vault:8200
VAULT_MOUNT_POINT=kv
VAULT_CLIENTS_PATH=dex
VAULT_APPROLE_ROLE_ID=...
VAULT_APPROLE_SECRET_PATH=/vault/secrets/secret-id
```

The image runs as uid 65532 and serves `/metrics`, `/healthz` and `/readyz` on port 8000.
Images are published for `linux/amd64` and `linux/arm64`.

Build it from the repository root:

```sh
docker build -f docker/image/Dockerfile -t dexus-vault .
```

For all configuration options see the [README](https://github.com/ifurs/dexus-vault#-configuration).
