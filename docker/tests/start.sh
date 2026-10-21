#!/usr/bin/env bash
# Usage: ./start.sh up [--with-dexus] | seed | down
set -euo pipefail
cd "$(dirname "$0")"

vault() { docker compose exec -T vault vault "$@"; }

seed() {
    vault secrets enable -path=kv kv-v2 >/dev/null 2>&1 || true
    for file in templ/client*.json; do
        name=$(basename "$file" .json)
        vault kv put "kv/dex/$name" "@/templ/$name.json" >/dev/null
    done
    vault policy write dexus-vault /templ/policy1.hcl >/dev/null
    token=$(vault token create -policy=dexus-vault -field=token)
    cat > .env <<ENV
VAULT_ADDR=http://127.0.0.1:8200
VAULT_TOKEN=$token
VAULT_MOUNT_POINT=kv
VAULT_CLIENTS_PATH=dex
DEX_GRPC_URL=127.0.0.1:5557
LOG_LEVEL=DEBUG
SYNC_INTERVAL=30
ENV
    echo "Seeded kv/dex with $(ls templ/client*.json | wc -l) clients, wrote $(pwd)/.env"
}

case "${1:-}" in
    up)
        docker compose up -d --wait dex vault
        seed
        if [ "${2:-}" = "--with-dexus" ]; then
            docker compose --profile dexus up -d --build dexus-vault
            echo "dexus-vault metrics: http://127.0.0.1:8000/metrics"
        else
            echo "Run from the repo root: dexus-vault --env-file docker/tests/.env"
        fi
        ;;
    seed) seed ;;
    down)
        docker compose --profile dexus down --remove-orphans
        rm -f .env
        ;;
    *)
        echo "usage: $0 up [--with-dexus] | seed | down" >&2
        exit 1
        ;;
esac
