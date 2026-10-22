#!/usr/bin/env bash
# Security scanners for dexus-vault, with fixed arguments and pinned versions.
# The dexus-security-auditor agent may run scanners only through this script.
#
# Usage: scripts/agents/scan.sh deps|workflows|code|secrets|dockerfile|image|all
set -euo pipefail

cd "$(dirname "$0")/../.."

ZIZMOR=zizmor@1.31.1
BANDIT=bandit@1.9.2
GITLEAKS=zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
HADOLINT=hadolint/hadolint:v2.15.1@sha256:32dac94127fd60b7b7e3fbfc65e1383b9b5e25c9bfd7b8536de7a539fe68a12d
TRIVY=aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c
AUDIT_IMAGE=dexus-vault:audit

find_uv() {
    for candidate in "$(command -v uv || true)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            echo "$candidate"
            return
        fi
    done
    echo "uv is not installed, see https://docs.astral.sh/uv/getting-started/installation/" >&2
    return 1
}

deps() {
    "$(find_uv)" audit --preview-features audit-command --frozen
}

workflows() {
    local uv token
    uv=$(find_uv)
    # online audits (known-vulnerable actions) need a token, offline otherwise
    token=$(gh auth token 2> /dev/null || true)
    if [ -n "$token" ]; then
        GH_TOKEN=$token "$uv" tool run "$ZIZMOR" --persona auditor .github
    else
        "$uv" tool run "$ZIZMOR" --offline --persona auditor .github
    fi
}

code() {
    "$(find_uv)" tool run "$BANDIT" -q -r dexus_vault scripts -x dexus_vault/grpc_dexidp
}

secrets() {
    docker run --rm -v "$PWD:/repo:ro" "$GITLEAKS" git /repo --redact --no-banner
}

dockerfile() {
    docker run --rm -i "$HADOLINT" < docker/image/Dockerfile
}

image() {
    docker build -q -f docker/image/Dockerfile -t "$AUDIT_IMAGE" . > /dev/null
    local status=0
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock:ro -v trivy-cache:/root/.cache \
        "$TRIVY" image --quiet --scanners vuln,secret,misconfig --severity HIGH,CRITICAL "$AUDIT_IMAGE" || status=$?
    echo "--- fixable only:"
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock:ro -v trivy-cache:/root/.cache \
        "$TRIVY" image --quiet --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "$AUDIT_IMAGE" || status=$?
    docker image rm -f "$AUDIT_IMAGE" > /dev/null
    return $status
}

run() {
    echo "=== $1"
    if "$1"; then
        echo "=== $1: ok"
    else
        echo "=== $1: FAILED ($?)"
        return 1
    fi
}

case "${1:-}" in
    deps | workflows | code | secrets | dockerfile | image)
        run "$1"
        ;;
    all)
        failed=0
        for scan in deps workflows code secrets dockerfile image; do
            run "$scan" || failed=1
        done
        exit $failed
        ;;
    *)
        echo "usage: $0 deps|workflows|code|secrets|dockerfile|image|all" >&2
        exit 1
        ;;
esac
