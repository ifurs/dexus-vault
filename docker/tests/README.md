# Local testing

Docker Compose stack for development and the integration tests.

> :warning: **Not suitable for production**: Vault runs in dev mode (in-memory, unsealed, root token `root`) and Dex gRPC has no TLS.

## Services

| service | port | |
|:---|:---|:---|
| Dex | 5556 (web), 5557 (gRPC) | [conf/dex.config.docker.yaml](conf/dex.config.docker.yaml) |
| Vault | 8200 | dev server, root token `root` |
| SSM (moto) | 5050 | AWS API emulator, any credentials work |
| dexus-vault | 8000 (metrics) | only with `--with-dexus`, built from this checkout |

## Usage

```sh
./start.sh up                # start everything, load sample clients, write .env and .env.ssm
./start.sh up --with-dexus   # same, and run dexus-vault in a container
./start.sh seed              # load the sample clients again
./start.sh down              # remove everything
```

`up` creates a KV v2 engine `kv`, writes [templ/client*.json](templ) to `kv/dex/`, creates a token limited by [templ/policy1.hcl](templ/policy1.hcl) and writes it to `.env`. It also writes the same clients as SecureString parameters under `/dex/clients` in the SSM emulator, with settings in `.env.ssm`. Then run dexus-vault from the repository root:

```sh
dexus-vault --env-file docker/tests/.env       # Vault backend
dexus-vault --env-file docker/tests/.env.ssm   # AWS SSM backend
```

Some sample clients are broken on purpose, to show how they are reported:

| secret | result |
|:---|:---|
| client1 | valid, uses every field |
| client2 | valid, minimal |
| client3 | valid, id from the secret name, warns about the unknown `client_id` key |
| client4 | valid public client, `public` given as a string |
| client5 | invalid, no secret |
| client6 | invalid, not a client at all |

## Integration tests

With the stack running:

```sh
DEXUS_INTEGRATION=1 uv run pytest tests/integration
```

The tests use the root token and the dev server's `secret/` engine, and random parameter paths in the SSM emulator, and clean up after themselves.

## TLS

To try gRPC with mutual TLS, generate certificates (for example with [this script](https://github.com/dexidp/dex/tree/master/examples/grpc-client)), mount them into the `dex` service, set `tlsCert`, `tlsKey` and `tlsClientCA` in the Dex config, and set `DEX_CA_CRT`, `DEX_CLIENT_CRT` and `DEX_CLIENT_KEY` for dexus-vault.
