---
name: security-audit
description: Security audit procedure for dexus-vault — the scanner suite (uv audit, zizmor, bandit, gitleaks, hadolint, Trivy), the project threat model, and how to judge and report findings. Use for a full audit, before a release, or when reviewing security-relevant changes.
argument-hint: "[full | diff <base>]"
---

# Security audit

Mode: `$ARGUMENTS` (default `diff main...HEAD`; `full` audits the whole repository).

## 1. Scanners

Run all of them in a full audit; in diff mode run the ones that cover the changed areas. Every command is read-only (scanner images get read-only mounts).

```bash
uv audit --preview-features audit-command --frozen                 # known vulnerabilities in uv.lock
GH_TOKEN=$(gh auth token) uvx zizmor@1.31.1 --persona auditor .github   # workflows, incl. known-vulnerable actions
uvx bandit@1.9.2 -q -r dexus_vault scripts -x dexus_vault/grpc_dexidp
docker run --rm -v "$PWD":/repo:ro zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner
docker run --rm -i hadolint/hadolint:v2.15.1 < docker/image/Dockerfile
docker build -q -f docker/image/Dockerfile -t dexus-vault:audit .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock:ro -v trivy-cache:/root/.cache \
  aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c \
  image --scanners vuln,secret,misconfig --severity HIGH,CRITICAL dexus-vault:audit
docker image rm -f dexus-vault:audit
```

Also check what scanners miss: every `uses:` SHA in `.github/` exists (`gh api repos/<owner>/<repo>/commits/<sha>`), and its version comment matches the tag it points to.

## 2. Threat model

| asset | why it matters |
|:---|:---|
| Dex client secrets | read from Vault/SSM, sent to Dex; leaking one lets an attacker impersonate that OAuth client |
| Vault token, AppRole secret id, Kubernetes JWT, AWS credentials | read access to every client secret |
| Dex gRPC admin API | full control over every OAuth client in Dex |
| release pipeline (PyPI trusted publishing, Docker Hub token, signing identity) | a compromised release reaches every user |

| attacker | can |
|:---|:---|
| writer to the Vault path / SSM path | **create or change Dex clients**, including redirect URIs, `public` and `trusted_peers` (by design: that path is a privileged interface; flag changes that widen it, e.g. pruning beyond the configured prefix) |
| network position between dexus-vault and Vault/AWS/Dex | read or alter traffic when TLS is off or unverified |
| contributor opening a pull request | runs CI code; must not reach secrets, write tokens or release jobs |
| compromised upstream action, image or package | runs inside CI or the image; contained by SHA pins, digests, the lockfile and cooldowns |

## 3. What to check by hand

- Secret values never reach logs, exceptions, metric labels, `repr`, CLI errors (`include_input=False`, `SecretStr`), including new code paths and error branches.
- TLS: verification stays on by default for Vault, Dex and AWS; insecure settings warn.
- Destructive operations (delete/recreate/prune) cannot be triggered by partial, empty or malformed source data.
- Credentials: tokens created by dexus-vault are revoked on exit; files are read, not logged; nothing is written to disk.
- Workflows: no `pull_request_target` or `workflow_run` with checkout of PR code; `${{ }}` only via `env:` in `run:`; least-privilege `permissions`; `persist-credentials: false`; no caches in release jobs; release only from `main` after review.
- Container: non-root, no pip, base images pinned by digest.

## 4. Judging findings

Report a finding only when you are at least 80% sure it is exploitable, and give a concrete attack: who, with what access, does what, and gets what. Before reporting, try to refute it: is the input really attacker-controlled, does an existing check stop it, is it test-only code?

Do not report: denial of service or resource exhaustion; missing hardening without a concrete exploit; outdated dependencies (the scanners own that); findings in tests or docs; log injection; theoretical races; unfixed base-image CVEs already recorded as accepted in memory.

## 5. Report

For each finding: severity (`critical` / `high` / `medium`), confidence (8–10), category, `file:line`, attack scenario, fix. Then scanner results as a table (tool, result, decisive line), and accepted risks you re-confirmed. End with `PASS` or `FAIL`.
