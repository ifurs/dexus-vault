# Local testing

Docs about running local testing

> :warning: **Caution: Not suitable for production use**: This setup may contain vulnerabilities. Please use with discretion. :grin:

## How to run it

run `docker-compose up -d` and do everything manually :neutral_face:

### Automated process

simply run with your shell(tested on bash and zsh):

```sh
./start.sh up

# with dexus_vault
./start.sh up dexus_vault
```

also script can clean everything that was created(except images)

```sh
./start.sh down

# with dexus_vault
./start.sh down dexus_vault
```

Here is going real magic :star2:! I'm kidding, that's just a shell script `start.sh` with sleep, that runs:

1. docker-compose up for Dex and Vault services, by default they are accessible on localhost:

    - `5556` Dex Web port
    - `5557` Dex GRPC port
    - `8200` Vault UI and API

2. configure Vault:

    - initialize
    - unseal
    - enable secrets kv called "kv"

3. add samples to Vault:

    - create client secrets under path `kv/dex`, some of them have wrong structure, just to show you exceptions
    - create simple policy for read and list under `kv/dex` path, so if you want to view from UI, type full path, or change policy
    - create token with policy from previous step

4. (Optional) If you specify "dexus_vault" as second argument for script, it will also start dexus_vault latest container and start syncing Dex with Vault. You can skip next steps if you choose to run with dexus_vault, env file will be generated automatically

5. After all steps above, you will get something like this:

    ```sh
        ______ Use this token to access client secrets in Vault _______
        export VAULT_TOKEN=...
    ```

6. Generate env file(if run from source) or set in env next variables:

    ```sh
    VAULT_TOKEN=<token_from_step_5>
    VAULT_ADDR=http://127.0.0.1:8200
    VAULT_MOUNT_POINT=kv
    VAULT_CLIENTS_PATH=dex
    ```

By default it enables Dex GRPC insecure, but still, you can use any cert gen script, like [this](https://github.com/dexidp/dex/tree/master/examples/grpc-client) to generate certs and add them to [docker-compose.yaml](docker-compose.yaml) and [dex.config.docker.yaml](conf/dex.config.docker.yaml)

## Troubleshooting

- `sh: permission denied: ./start.sh` simply add execute permissions for script `chmod +x start.sh`
