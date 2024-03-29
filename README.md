# DEXUS VAULT

[![Latest Github release](https://img.shields.io/github/tag/ifurs/dexus-vault.svg)](https://github.com/ifurs/dexus-vault/releases/latest)
![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

## **dexus-vault** - synchronizer of Dex clients with secrets in Vault

## 🚩 Table of Contents

- [About the project](#-about-the-project)
  - [How it works](#how-it-works)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
  - [General](#general)
  - [Dex client configuration](#dex-client-configuration)
    - [About Dex auth](#about-dex-auth)
  - [Vault client configuration](#vault-client-configuration)
    - [About Vault auth](#about-vault-auth)
- [Vault secret structure](#-vault-secret-structure)
- [Local Testing](#-local-testing)
- [Other notes](#-other-notes)
- [Thanks](#-thanks)

## 🚀 About the project

Dexus Vault is utility designed to synchronize Dex client configurations with secrets stored in Hashicorp Vault.
This tool simplifies the management of Dex clients by automating the process of keeping them in sync with Vault secrets.

### How it works
When you execute `dexus-vault`, it establishes a connection to the specified Vault using the `hvac` library and retrieves secrets from the provided path. Following this, `dexus-vault` connects to Dex IdP via gRPC and creates or updates clients.

> Please note that Dex does not currently support a native "Update" method. As a workaround, `dexus_vault` will recreate the client. Be aware of this behavior when using the tool.

## 💾 Installation

The recommended installation method is using `pip`:

```bash
pip install dexus-vault
```

Using `docker`:

```bash
docker run ifurs/dexus-vault
```
you can find docker image [here](https://github.com/ifurs/dexus-vault/docker/image)

## 📙 Usage

if you've installed `dexus-vault` using `pip`, you can execute it with the following command:

```bash
dexus-vault
```
or like a python module:

```bash
python3 -m dexus_vault
```

This will initiate a process that synchronizes Dex clients with the secrets stored in Vault.

## 🔧 Configuration

Currently dexus-vault support only Environment variables.

### General

| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| SYNC_INTERVAL | false | 60    | Interval in seconds, dexus_vault will refresh in |
| LOG_LEVEL | false | INFO | Set log level(logging lib) |
| METRICS_ENABLE | false | True | Enable prometheus metrics publisher |
| METRICS_PORT | false | 8000 | Set Metrics port, reuire METRICS_ENABLE to be enabled |
| INTERNAL_METRICS | false | False | Enable the built-in metrics for Python (not application-specific) |

### Dex client configuration

| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| DEX_GRPC_URL | false | 127.0.0.1:5557 | url, with your dex grpc |
| CLIENT_CRT | false | - | path to Dex GRPC client certificate |
| CLIENT_KEY | false | - | path to Dex GRPC client certificate key |
| CA_CRT | false | - | path to Dex GRPC client certificate autority |
| DEX_MAX_RETRIES | false | 20 | How many retries need to wait for Dex to be reacheble |
| DEX_RETRY_WAIT | false | 3 | How many seconds need to wait before next retry |

### Vault client configuration

| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| VAULT_ADDR | false | http://127.0.0.1:8200 | vault adress |
| VAULT_CLIENTS_PATH | true | - | path in vault where clients could be found |
| VAULT_MOUNT_POINT | false | - | vault [mount point](https://developer.hashicorp.com/vault/tutorials/enterprise/namespace-structure#understand-vault-s-mount-points) |
| VAULT_TOKEN | false | - | used to auth to Vault via token |
| VAULT_CERT | false | - | Vault client certificate path |
| VAULT_CERT_KEY | false | - | Vault client certificate key path |
| VAULT_CERT_CA | false | - | Vault certficate authority path or bool, `false` - do not validate, `true` - validate with internal trustore |
| VAULT_LDAP_USERNAME | false | - | LDAP username used to auth to Vault |
| VAULT_LDAP_PASSWORD | false | - | LDAP password used to auth to Vault |
| VAULT_APPROLE | false | - | bool value, used to identify to use APPROLE auth |
| VAULT_APPROLE_ROLE_ID | false | - | Vault approle role id |
| VAULT_APPROLE_SECRET_ID | false | - | Vault approle secret id |
| VAULT_APPROLE_PATH | false | - | Vault approle path, use it if agent mount approle file in other than default directory |
| VAULT_MAX_RETRIES | false | 20 | How many retries need to mark Vault unreacheble |
| VAULT_RETRY_WAIT | false | 3 | How many seconds need to wait before next retry |

#### About Dex auth

If you don't specify certificates for Dex, the client will establish an insecure connection. Note that it's not necessary to use a certificate authority when you provide a client certificate and key.

#### About Vault auth

There are several authentication methods available:

- Token-based authentication
- LDAP authentication
- Certificate-based authentication
- AppRole authentication: To use this method, set `VAULT_APPROLE` to `true`. The HVAC client will then log into Vault using the default file mounted by the Vault agent by default, also there is possible to specify approle id and secret via env vars too.

### Metrics

For now "dexus-vault" publish simplified metrics, like this:

```bash
client_create{client_id="my-first-dex-client", status="ok"} 1.0
```
for "status" could be values "ok" and "failed"

> **NOTE:** We plan to redesign the metrics system in the near future. Any contributions to this effort are greatly appreciated.

## 🔒 Vault secret structure

This example demonstrates all the parameters available for a client, which align with the Dex gRPC protocol message.

```json
{
  "id": "my-first-client",
  "secret": "",
  "logo_url": "https://picsum.photos/200/300",
  "name": "My First Client",
  "public": false,
  "redirect_uris": ["http://127.0.0.1:5000/callback"],
  "trusted_peers": ["my-second-client"]
}
```

In the Vault configuration, `id` and `secret` are mandatory fields. The `public` field defaults to `False` at the `dexus_vault` level. If you wish to enable `public`, ensure that it is set as a boolean type in your Vault implementation, not as a string.

For defining lists in `redirect_uris` and `trusted_peers`, there are two methods:

1. Use a native JSON list, e.g., `["value1", "value2"]`. Note that this will disable the non-JSON view for that secret in the Vault UI.
2. Use a string with commas as delimiters, e.g., `"value1,value2"`. However, this method is not recommended and may be deprecated in future versions.

## 💻 Local Testing

The `docker/tests` directory houses a `docker-compose.yaml` file, designed to facilitate local testing by running both Vault and Dex. However, this configuration is not suitable for production environments.

For more details, please see the [README](docker/tests/README.md).

## 📓 Other notes
- This projects uses pre-commit: https://pre-commit.com/

- All gRPC API methods dexus_vault use, defined in [api.proto](https://github.com/dexidp/dex/blob/v2.38.0/api/v2/api.proto)
and compiled with `grpc_tools.protoc`

## Roadmap

Plans for future:

- [ ] Redesign metrics concept to make it more Prometheus friendly
- [ ] Switch to pydantic
- [ ] Implement functionality that tracks current clients state in Dex
- [ ] Make logs more Fluent
- [ ] Redisign dexus-vault to work like cli and accepts params
- [ ] Implement feature to use other storage options

## 🔥 Thanks
- [Hurlenko](https://github.com/hurlenko) for references copied from your repos
