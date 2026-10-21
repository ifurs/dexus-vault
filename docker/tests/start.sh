#!/usr/bin/env bash
# Usage: ./start.sh up [--with-dexus] | seed | down
set -euo pipefail
cd "$(dirname "$0")"

vault() { docker compose exec -T vault vault "$@"; }

# writes templ/client*.json as SecureString parameters under /dex/clients,
# using the boto3 that ships with the moto image
seed_ssm() {
    docker compose exec -T ssm python3 - <<'PY'
import glob, os, boto3
ssm = boto3.client("ssm", endpoint_url="http://127.0.0.1:5000", region_name="eu-west-1",
                   aws_access_key_id="testing", aws_secret_access_key="testing")
for path in sorted(glob.glob("/templ/client*.json")):
    name = os.path.basename(path)[:-5]
    with open(path) as file:
        ssm.put_parameter(Name=f"/dex/clients/{name}", Value=file.read(),
                          Type="SecureString", Overwrite=True)
PY
    cat > .env.ssm <<ENV
SECRETS_BACKEND=aws-ssm
SSM_PATH=/dex/clients
SSM_ENDPOINT_URL=http://127.0.0.1:5050
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=testing
AWS_SECRET_ACCESS_KEY=testing
DEX_GRPC_URL=127.0.0.1:5557
LOG_LEVEL=DEBUG
SYNC_INTERVAL=30
ENV
    echo "Seeded SSM /dex/clients, wrote $(pwd)/.env.ssm"
}

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
        docker compose up -d --wait dex vault ssm
        seed
        seed_ssm
        if [ "${2:-}" = "--with-dexus" ]; then
            docker compose --profile dexus up -d --build dexus-vault
            echo "dexus-vault metrics: http://127.0.0.1:8000/metrics"
        else
            echo "Run from the repo root: dexus-vault --env-file docker/tests/.env"
            echo "             or for SSM: dexus-vault --env-file docker/tests/.env.ssm"
        fi
        ;;
    seed) seed && seed_ssm ;;
    down)
        docker compose --profile dexus down --remove-orphans
        rm -f .env .env.ssm
        ;;
    *)
        echo "usage: $0 up [--with-dexus] | seed | down" >&2
        exit 1
        ;;
esac
