"""
The hook guards in scripts/agents/guard.py, run the way Claude Code runs them.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "agents" / "guard.py"


def run(mode, event):
    return subprocess.run(
        [sys.executable, str(GUARD), mode],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=60,
    )


def bash(command):
    return run(
        "bash-readonly", {"tool_name": "Bash", "tool_input": {"command": command}}
    )


@pytest.mark.parametrize(
    "command",
    [
        "git log --oneline -5",
        "git diff main...HEAD",
        "curl -sf https://raw.githubusercontent.com/dexidp/dex/v2.46.0/api/v2/api.proto",
        "curl -sf https://api.github.com/repos/dexidp/dex/releases/latest | grep tag_name",
        "pip index versions grpcio 2>/dev/null | head -1",
        "python -c 'import hvac; print(hvac.__version__)' > /dev/null",
        "gh api repos/dexidp/dex/releases --jq '.[0].tag_name'",
        "gh pr view 37",
        "pytest -q tests/test_models.py",
        "docker compose ps",
        "grep -rn 'UpdateClient' dexus_vault 2>&1",
    ],
)
def test_read_only_commands_are_allowed(command):
    assert bash(command).returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "git commit -am wip",
        "git push origin HEAD",
        "git checkout -- dexus_vault/sync.py",
        "pip install boto3",
        "rm -rf build",
        "sed -i 's/a/b/' dexus_vault/models.py",
        "echo hi > dexus_vault/new.py",
        "cat x >> README.md",
        "docker compose up -d",
        "gh pr merge 37",
        "gh api -X POST repos/ifurs/dexus-vault/issues",
        "curl -X DELETE https://example.com/thing",
        "curl --data 'a=b' https://example.com",
        "kubectl apply -f deploy.yaml",
        "aws ssm put-parameter --name /x --value y",
        "vault kv put secret/dex/app secret=s",
        "ls && touch marker",
    ],
)
def test_mutating_commands_are_blocked(command):
    result = bash(command)
    assert result.returncode == 2, command
    assert "read-only" in result.stderr


def edit(path, cwd=ROOT):
    return run(
        "tests-only",
        {"tool_name": "Edit", "tool_input": {"file_path": str(path)}, "cwd": str(cwd)},
    )


def test_test_files_may_be_edited():
    assert edit(ROOT / "tests" / "test_sync.py").returncode == 0
    assert edit(ROOT / "tests" / "integration" / "new_test.py").returncode == 0
    assert edit(ROOT / "docker" / "tests" / "templ" / "client9.json").returncode == 0


def test_relative_paths_resolve_against_cwd():
    assert edit("tests/test_sync.py").returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "dexus_vault" / "sync.py",
        ROOT / "README.md",
        ROOT / "tests" / ".." / "dexus_vault" / "dex.py",
        ROOT / "docker" / "tests" / "start.sh",
        Path("/etc/passwd"),
    ],
)
def test_other_files_are_blocked(path):
    result = edit(path)
    assert result.returncode == 2
    assert "only edit" in result.stderr


def test_verify_lets_the_second_stop_through():
    assert run("verify", {"stop_hook_active": True, "cwd": str(ROOT)}).returncode == 0


def test_verify_blocks_on_failing_checks(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "test_fail.py").write_text("def test_fails():\n    assert 1 == 2\n")
    result = run("verify", {"stop_hook_active": False, "cwd": str(tmp_path)})
    assert result.returncode in (1, 2)
    if result.returncode == 2:
        assert "Verification gate failed" in result.stderr


def test_unknown_mode_is_an_error():
    assert run("nope", {}).returncode == 1


def test_verify_uses_uv_with_a_lockfile(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "uv.lock").write_text("")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # a fake uv that records how it was called and fails
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\necho "uv $*" >&2\nexit 3\n')
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    result = run("verify", {"stop_hook_active": False, "cwd": str(tmp_path)})
    assert result.returncode == 2
    assert "uv run --frozen black --check" in result.stderr
