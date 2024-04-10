#!/bin/bash

# command "up" or "down"
arg1=$1
# argument "dexus_vault" or empty
arg2=$2

# TODO: remove export and exec in alias
alias exec_vault=`docker exec -ti vault`
export VAULT_ADDR="http://127.0.0.1:8200"

parse_vault_response() {
    local response="$1"

    # Extract unseal keys
    unseal_key_1=$(echo "$response" | grep 'Unseal Key 1:' | awk '{print $NF}')
    unseal_key_2=$(echo "$response" | grep 'Unseal Key 2:' | awk '{print $NF}')
    unseal_key_3=$(echo "$response" | grep 'Unseal Key 3:' | awk '{print $NF}')
    unseal_key_4=$(echo "$response" | grep 'Unseal Key 4:' | awk '{print $NF}')
    unseal_key_5=$(echo "$response" | grep 'Unseal Key 5:' | awk '{print $NF}')

    # Extract initial root token
    initial_root_token=$(echo "$response" | grep 'Initial Root Token:' | awk '{print $NF}')

    # Print the extracted values
    echo "Unseal Key 1: $unseal_key_1"
    echo "Unseal Key 2: $unseal_key_2"
    echo "Unseal Key 3: $unseal_key_3"
    echo "Unseal Key 4: $unseal_key_4"
    echo "Unseal Key 5: $unseal_key_5"
    echo "Initial Root Token: $initial_root_token"
}

start_docker_compose() {
    docker-compose up -d
    echo '\033[0;32m started docker-compose dex and vault, pls wait until it will init \033[0m'
    sleep 10
}

function down_docker_compose() {
    if [ "$arg2" = "dexus_vault" ]; then
        docker-compose -f docker-compose.dexus_vault.yml down
        rm .env
    fi
    docker-compose down
    echo '\033[0;32m docker-compose down \033[0m'
}

vault_unseal() {
    local unseal_key="$1"
    exec_vault vault operator unseal $unseal_key > /dev/null
}

vault_init() {
    response=$(exec_vault vault operator init)
    sleep 3
    parse_vault_response "$response"
    vault_unseal $unseal_key_1
    vault_unseal $unseal_key_2
    vault_unseal $unseal_key_3
    vault_unseal $unseal_key_4
    vault_unseal $unseal_key_5
    exec_vault vault status
}

vault_enable_kv() {
    exec_vault vault login $initial_root_token > /dev/null
    exec_vault vault secrets enable -version=2 kv > /dev/null
    exec_vault vault kv enable-versioning kv/ > /dev/null
}

vault_create_secrets() {
    exec_vault vault kv put kv/dex/client1 @templ/client1.json > /dev/null
    exec_vault vault kv put kv/dex/client2 @templ/client2.json > /dev/null
    exec_vault vault kv put kv/dex/client2 @templ/client3.json > /dev/null
    exec_vault vault kv put kv/dex/client2 @templ/client4.json > /dev/null
}

vault_create_test() {
    vault_enable_kv
    vault_create_secrets
    exec_vault vault policy write policy1 templ/policy1.hcl > /dev/null
    echo "\033[0;32m______ Use this token to access client secrets in Vault _______\033[0m"
    exec_vault vault token create -policy=policy1
}

generate_dotenv() {
    echo "DEX_GRPC_URL=dexidp:5557" > .env
    echo "VAULT_ADDR=http://vault:8200" >> .env
    echo "VAULT_TOKEN=$initial_root_token" >> .env
    echo "VAULT_CLIENTS_PATH=/dex" >> .env
    echo "VAULT_MOUNT_POINT=kv" >> .env
}

run_dexus_vault() {
    generate_dotenv
    docker-compose -f docker-compose.dexus_vault.yml up -d
}

init_all() {
    start_docker_compose
    vault_init
    vault_create_test
    if [ "$arg2" = "dexus_vault" ]; then
        echo "Starting dexus_vault..."
        run_dexus_vault
    fi
}

trap down_docker_compose SIGINT

if [ "$arg1" = "down" ]; then
    down_docker_compose
    exit 0
fi

if [ "$arg1" = "up" ]; then
    init_all
    exit 0
fi
