# Security policy

## Supported versions

Security fixes go into the latest release. Upgrade to it before reporting.

## Reporting a vulnerability

Do not open a public issue. Use [private vulnerability reporting](https://github.com/ifurs/dexus-vault/security/advisories/new) and include the version, configuration (without secrets) and steps to reproduce. You can expect a first answer within a week.

dexus-vault handles Dex client secrets and credentials for Vault and AWS, so reports about secrets leaking into logs, errors or metrics, about TLS handling, and about Dex clients being changed or deleted unexpectedly are especially welcome.

## Verifying releases

Every release is built by GitHub Actions from `main` after a pull request bumps the version; no release starts from a hand-pushed tag or a manual run. Which changes reach `main` is governed by the repository's branch rules (see README "Releasing").

**PyPI packages** are uploaded with trusted publishing and carry [PEP 740](https://peps.python.org/pep-0740/) attestations. The same files with Sigstore signatures are attached to the GitHub release:

```bash
uvx pypi-attestations verify pypi --repository https://github.com/ifurs/dexus-vault \
  pypi:dexus_vault-<version>-py3-none-any.whl
```

**Docker images** on Docker Hub are signed with cosign (keyless) and ship SBOM and provenance attestations:

```bash
cosign verify ifurs/dexus-vault:<version> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity 'https://github.com/ifurs/dexus-vault/.github/workflows/docker-publish.yml@refs/heads/main'
docker buildx imagetools inspect ifurs/dexus-vault:<version> --format '{{ json .SBOM }}'
```

The signature identity names the workflow, not the source commit. To check that an image was built from the tagged commit, compare the image's `org.opencontainers.image.revision` label (also recorded in the provenance attestation and as the `commit` signature annotation) with `git rev-parse <version>^{commit}`. Images up to 0.3.1 were signed by the old tag-triggered workflow, with identity `.../docker-publish.yml@refs/tags/<version>`.
