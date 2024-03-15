# DEXUS VAULT
Synchronizer of Dex clients with secrets in Vault

[![Latest Github release](https://img.shields.io/github/tag/ifurs/dexus-vault.svg)](https://github.com/ifurs/dexus-vault/releases/latest)
![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

## Intro
Dexus Vault is utility designed to synchronize Dex client configurations with secrets stored in Hashicorp Vault.
This tool simplifies the management of Dex clients by automating the process of keeping them in sync with Vault secrets.

## How it works
when you run dexus_vault, it will connects to provided Vault via `hvac` library and collets secrets by provided path, then dexus_vault conncets to Dex Idp over GRPC and create/update clients.

Currently Dex don't have native "Update" method, so dexus_vault will recreate client(keep in mind)

## How to install
The recommended installation method is using pip:
```sh
pip install dexus-vault
```
and run it:
```sh
python -m dexus_vault
```

## Run dexus_vault
simply run
```sh
python3 -m dexus_vault
```
and it will start worker that syncs Dex clients with Vault secrets

## Configuration
### General
| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| SYNC_INTERVAL | false | 60    | interval in seconds, dexus_vault will refresh in |

### Dex client configuration
| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| DEX_GRPC_URL | false | 127.0.0.1:5557 | url, with your dex grpc |
| CLIENT_CRT | false | - | path to Dex GRPC client certificate |
| CLIENT_KEY | false | - | path to Dex GRPC client certificate key |
| CA_CRT | false | - | path to Dex GRPC client certificate autority |

#### About Dex auth
if you not specified in dex certificates, simply skip them, and client will start insecure connection, also it is not required to use certificate authority when you specify client crt and client key.

### Vault client configuration
| variable | required  | default | description |
|:---------:|:---------:|:-------:|:------------:|
| VAULT_ADDR | false | http://127.0.0.1:8200 | vault adress |
| VAULT_CLIENTS_PATHS | true | - | path in vault where clients could be found |
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

#### About Vault auth
You can choose any of:
- token based
- ldap
- with cert
- using approle, for that you need simply set `VAULT_APPROLE` to true, and when start, hvac will login to Vault via default maunted file by vault agent

## Vault secret structure
This example shows all available params for client(same as proto message)
```json
{
  "id": "my-first-client",
  "secret": "", // put here your client secret
  "logo_url": "https://picsum.photos/200/300", // example logo, not recommended
  "name": "My First Client",
  "public": false,
  "redirect_uris": ["http://127.0.0.1:5000/callback"],
  "trusted_peers": ["my-second-client"]
}
```
In Vault config `id` and `secret` are required, and `public` has default value `False` that enforced on dexus_vault level.
For `public` default value is "False" but if you want to enable, plz, check if that var has bool type(Vault implementation), not a string.
Also you may ask, how to define lists for `redirect_uris` and `trusted_peers`, you can do it in 2 ways:
- native json list `["value1", "value2"]` but this will disale in Vault UI non-json view for that secret
- using string with comma as delimeter `"value1,value2"` but it's not recommended and would be removed in future iterations

## Local Testing
The `docker/tests` directory contains a `docker-compose.yaml` file. This file is configured to run Vault and Dex locally for testing purposes. Please note that this setup is not intended for production use.

For additional information, refer to the [README](docker/tests/README.md) in the `docker/tests` directory.

## About Dex GRPC
All GRPC API methods dexus_vault use, defined in [api.proto](https://github.com/dexidp/dex/blob/v2.38.0/api/v2/api.proto)
and compiled with `grpc_tools.protoc`

## Other notes
This projects uses pre-commit: https://pre-commit.com/

# THANKS
- [Hurlenko](https://github.com/hurlenko) for references copied from your repos
