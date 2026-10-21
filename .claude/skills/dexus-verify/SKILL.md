---
name: dexus-verify
description: The verification gate for dexus-vault. Use before claiming any change works, is fixed or is done, before committing, and when reporting results from an agent; lists the exact commands per kind of change and how to report evidence.
---

# Verification gate

No claim that something works, passes or is fixed without output from a command run **in this turn** that shows it. "Should pass", an earlier run, or another agent's report is not evidence.

## Which checks

| change touches | run |
|:---|:---|
| anything | `black --check . && ruff check . && pytest -q` |
| `sources/`, `dex.py`, `sync.py`, `cli.py`, `docker/tests/` | also `docker/tests/start.sh up` then `DEXUS_INTEGRATION=1 pytest -q tests/integration` |
| `docker/image/`, `pyproject.toml`, `requirements*.txt` | also `docker build -f docker/image/Dockerfile .` and `python -m build` |
| CLI behavior or exit codes | also run `dexus-vault --env-file docker/tests/.env --once` (or `.env.ssm`) and check `echo $?` |
| `.github/workflows/` | parse every changed YAML file; CI itself only runs after a push |

Start the compose stack only if it is not running (`docker compose -f docker/tests/docker-compose.yaml ps`), and stop it again if you started it.

## Regression tests must be proven

A test for a bug counts only after a red-green check: run it against the unfixed code and see it fail **for the reported reason**, then pass with the fix. If the fix is already in place, temporarily revert it (or the relevant line), run, restore, run.

## Reporting

Quote the command and the decisive output line, for example:

```text
$ pytest -q
96 passed, 6 skipped in 2.77s
```

Report skipped suites explicitly (integration tests skip without `DEXUS_INTEGRATION=1`, SSM tests without boto3). If a check could not run, say which and why; never round it up to "passed".
