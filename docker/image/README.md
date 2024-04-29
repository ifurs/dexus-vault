# DEXUS VAULT

[![Latest Github release](https://img.shields.io/github/tag/ifurs/dexus-vault.svg)](https://github.com/ifurs/dexus-vault/releases/latest)
![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

## **dexus-vault** - synchronizer of Dex clients with secrets in Vault

## Usage

Provide env vars for that image with your configuration of Dex and Vault, example env:

```sh
SYNC_INTERVAL=20
LOG_LEVEL="DEBUG"
DEX_GRPC_URL="127.0.0.1:5557"
VAULT_ADDR="https://127.0.0.1:8200"
# example for path kv/dex/*
VAULT_MOUNT_POINT="kv"
VAULT_CLIENTS_PATH="dex"
VAULT_TOKEN=...
```

For more configuration options check [README](https://github.com/ifurs/dexus-vault/README.md)
