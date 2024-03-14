# LOCAL TESTING
Section about running local testing

> :warning: **Do not use it in your production**: there viruses! :grin:
## How to run it
run `docker-compose up -d` and do everything manualy :neutral_face:

### Automated proces
simply run with your shell(tested on bash and zsh):

```sh
./start.sh
```

Here is going real magic :star2:! I'm kidding, that's just a shell script `start.sh` with sleep, that runs:
1. docker-compose up for Dex and Vault services, by default they are accesible on localhost:
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

4. after all steps, you will get something like this:
    ```sh
        ______ Use this token to access client secrets in Vault _______
        Key                  Value
        ---                  -----
        token                hvs.CAESINAH6-fnernJHBHJBVUHVvvuyvuwvweefw
        token_accessor       JBHbuyguybBHHJDU
        token_duration       768h
        token_renewable      true
        token_policies       ["default" "policy1"]
        identity_policies    []
        policies             ["default" "policy1"]
    ```
    just copy `token` and add it to your env `VAULT_TOKEN=...`

By default it enables Dex GRPC insecure, but still, you can use any cert gen script, like [this](https://github.com/dexidp/dex/tree/master/examples/grpc-client) to generate certs and add them to [docker-compose.yaml](docker-compose.yaml) and [dex.config.docker.yaml](conf/dex.config.docker.yaml)
