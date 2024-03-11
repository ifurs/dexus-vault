# DEXUS VAULT
Simple tool that syncronize dex clients with vault secrets

## How to install
### from source
1. Clone the project
```
git clone https://github.com/ifurs/dexus-vault.git
```
2. Install package
```
python -m pip install --upgrade setuptools wheel
```

### from PyPi
Not this time:)

## Run

simply run
```
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
| VAULT_ADDR | false | https://127.0.0.1:8200 | vault adress |
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

#### About Vault auth
You can choose any of:
- token based
- ldap
- with cert
- using approle, for that you need simply set `VAULT_APPROLE` to true, and when start, hvac will login to Vault via default maunted file by vault agent

## Vault secret structure
```json
{
  "id": "my-first-client",
  "secret": "", // put here your client secret
  "logo_url": "https://picsum.photos/200/300", // example logo, do not use in your config
  "name": "My First Client",
  "public": false,
  "redirect_uris": "http://127.0.0.1:5000/callback",
  "trusted_peers": "my-second-client"
}
```
In Vault config `id` and `secret` are required, and `public` has default value `False` that enforced on dexus_vault level.
Also you may ask, how to define lists for `redirect_uris` and `trusted_peers`, you can do it in 2 ways:
- native json list `["value1", "value2"]` but this will disale in Vault UI non-json view for that secret
- using string with comma as delimeter `"value1,value2"` but it's not recommended and would be removed in future iterations

## Run local testing
In dir `docker/tests` you can find `docker-compose.yaml` that runs Vault and Dex localy, and `start.sh` that runs same but with predifined configuration, sample clients and create token with policy to work with dexus_vault, do not use that script in production, only for local testing

## About Dex GRPC
all GRPC Api methods dexus_vault use, defined in https://github.com/dexidp/dex/blob/v2.38.0/api/v2/api.proto
and compiled with `grpc_tools.protoc`

## Other notes
This projects use pre-commit: https://pre-commit.com/
