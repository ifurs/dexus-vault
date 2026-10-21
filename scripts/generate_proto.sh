#!/usr/bin/env bash
# Regenerate Dex gRPC Python stubs from proto/dexidp/api.proto.
# Usage: scripts/generate_proto.sh [dex-version]   (requires grpcio-tools)
# With a dex version (e.g. v2.46.0) the proto is downloaded first.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -n "${1:-}" ]; then
    curl -sfL -o proto/dexidp/api.proto \
        "https://raw.githubusercontent.com/dexidp/dex/$1/api/v2/api.proto"
fi

python -m grpc_tools.protoc \
    -I proto \
    --python_out=dexus_vault/grpc_dexidp \
    --grpc_python_out=dexus_vault/grpc_dexidp \
    dexidp/api.proto

# protoc emits a top-level import, make it absolute to the package
sed -i.bak 's/^from dexidp import api_pb2 as/import dexus_vault.grpc_dexidp.dexidp.api_pb2 as/' \
    dexus_vault/grpc_dexidp/dexidp/api_pb2_grpc.py
rm dexus_vault/grpc_dexidp/dexidp/api_pb2_grpc.py.bak
