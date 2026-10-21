#!/usr/bin/env python3
"""
Claude Code hook guards for the project agents in .claude/agents.

    guard.py bash-readonly   PreToolUse(Bash): block commands that change state
    guard.py bash-audit      like bash-readonly, but allows the security scanners
    guard.py tests-only      PreToolUse(Edit|Write): allow edits under tests/ only
    guard.py verify          SubagentStop: block finishing while lint or tests fail

Reads the hook input JSON on stdin. Exit 2 blocks, stderr is shown to the
agent. These are backstops for the agents' instructions, not a sandbox.
"""

import json
import re
import shutil

# only fixed lint/test commands are run, without a shell
import subprocess  # nosec B404
import sys
from pathlib import Path

# commands a read-only agent must not run
MUTATING = [
    r"\bgit\s+(commit|push|reset|checkout|switch|merge|rebase|stash|tag|clean|restore|rm|mv|add|apply|am|cherry-pick|revert|branch\s+-[dDmM])\b",
    r"\b(pip3?|uv|poetry|pipx|npm|apt(-get)?|brew)\s+(install|uninstall|add|remove|upgrade)\b",
    r"(^|[\s;&|(])(rm|mv|cp|chmod|chown|touch|mkdir|rmdir|ln|truncate|dd|tee)\s",
    r"\bsed\s+(-[a-zA-Z]*i|--in-place)",
    r"\bdocker\s+(compose\s+)?(run|up|down|rm|stop|kill|exec|build|push|create|start|restart)\b",
    r"\bgh\s+(pr|issue|release|repo|workflow|run|secret|variable|label)\s+(create|edit|merge|close|reopen|delete|comment|review|run|set|cancel|rerun)\b",
    r"\b(gh\s+api|curl|wget)\b.*(\s-X\s*|--method\s+|--request\s+)(POST|PUT|PATCH|DELETE)\b",
    r"\bcurl\b.*\s(-d|--data\S*|-F|--form|-T|--upload-file)\s",
    r"\b(kubectl|helm|terraform)\s+(apply|create|delete|patch|replace|install|upgrade|uninstall|destroy|import)\b",
    r"\baws\s+\S+\s+(put|delete|create|update|modify|remove|attach|detach|start|stop|terminate)-",
    r"\bvault\s+(write|delete|kv\s+(put|patch|delete|destroy|undelete|rollback)|secrets\s+(enable|disable)|auth\s+(enable|disable)|policy\s+(write|delete)|token\s+(create|revoke))\b",
    # output redirection into a file (stderr redirects and /dev/null are fine)
    r"(^|[^0-9&>])>>?\s*(?!/dev/null|&)[^\s&|;]",
]
EDITABLE_PREFIXES = ("tests/", "docker/tests/templ/")

# security scanner containers the audit agent may run, and the throwaway image it scans
SCANNER_IMAGES = ("aquasec/trivy", "zricethezav/gitleaks", "hadolint/hadolint")
AUDIT_IMAGE = "dexus-vault:audit"
NAMED_VOLUME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def _scanner_run(segment: str) -> bool:
    """
    `docker run --rm` of a scanner image whose bind mounts are all read-only.
    Named volumes (e.g. a trivy cache) are allowed, they never touch the host tree.
    """
    words = segment.split()
    if words[:3] != ["docker", "run", "--rm"]:
        return False
    if not any(
        word.startswith(f"{image}:") or word.startswith(f"{image}@")
        for word in words
        for image in SCANNER_IMAGES
    ):
        return False
    for flag, value in zip(words, words[1:], strict=False):
        if flag in ("-v", "--volume", "--mount"):
            source = value.split(":", 1)[0]
            # anything but a plain volume name is a host path and must be read-only
            if not NAMED_VOLUME.fullmatch(source) and not value.endswith(":ro"):
                return False
        if flag in ("--privileged", "--pid", "--network") or flag.startswith(
            "--cap-add"
        ):
            return False
    return True


def _audit_allowed(segment: str) -> bool:
    words = segment.split()
    if _scanner_run(segment):
        return True
    if (
        words[:2] == ["docker", "build"]
        and AUDIT_IMAGE in words
        and "--push" not in words
    ):
        return True
    return (
        words[:3] in (["docker", "image", "rm"], ["docker", "rmi", AUDIT_IMAGE])
        and words[-1] == AUDIT_IMAGE
    )


def _deny(reason: str) -> int:
    print(reason, file=sys.stderr)
    return 2


def bash_readonly(event: dict) -> int:
    command = event.get("tool_input", {}).get("command", "")
    for pattern in MUTATING:
        if re.search(pattern, command):
            return _deny(
                "Blocked: this agent is read-only and the command changes state "
                f"(matched {pattern!r}). Report what should be run instead."
            )
    return 0


def _repo_root(path: Path) -> Path | None:
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def tests_only(event: dict) -> int:
    tool_input = event.get("tool_input", {})
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return 0
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or ".") / path
    path = path.resolve()
    root = _repo_root(path.parent)
    relative = path.relative_to(root).as_posix() if root else None
    if relative is None or not relative.startswith(EDITABLE_PREFIXES):
        return _deny(
            f"Blocked: this agent may only edit {', '.join(EDITABLE_PREFIXES)} "
            f"(tried {raw}). Report product code bugs instead of fixing them."
        )
    return 0


def _tail(output: str, lines: int = 25) -> str:
    return "\n".join(output.strip().splitlines()[-lines:])


def verify(event: dict) -> int:
    if event.get("stop_hook_active"):
        # already continued once because of this gate, let the agent report
        return 0
    root = _repo_root(Path(event.get("cwd") or ".").resolve())
    if root is None:
        return 0
    checks = [
        ["black", "--check", "-q", "."],
        ["ruff", "check", "-q", "."],
        ["pytest", "-q", "-x", "-p", "no:cacheprovider"],
    ]
    if (root / "uv.lock").exists() and shutil.which("uv"):
        # the locked tool versions, the same ones CI uses
        checks = [["uv", "run", "--frozen", *command] for command in checks]
    for command in checks:
        if shutil.which(command[0]) is None:
            print(
                f"verify gate skipped: {command[0]} is not installed", file=sys.stderr
            )
            return 1
        # fixed argv, no shell, nothing taken from the hook input
        result = subprocess.run(  # nosec B603
            command, cwd=root, capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            return _deny(
                f"Verification gate failed: `{' '.join(command)}` exited "
                f"{result.returncode}. Fix it, or report the failure explicitly "
                f"as BLOCKED / DONE_WITH_CONCERNS.\n{_tail(result.stdout + result.stderr)}"
            )
    return 0


def bash_audit(event: dict) -> int:
    command = event.get("tool_input", {}).get("command", "")
    remaining = " ; ".join(
        segment
        for segment in SEGMENT_SPLIT.split(command)
        if not _audit_allowed(segment)
    )
    return bash_readonly({"tool_input": {"command": remaining}})


MODES = {
    "bash-readonly": bash_readonly,
    "bash-audit": bash_audit,
    "tests-only": tests_only,
    "verify": verify,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in MODES:
        print(f"usage: guard.py {{{','.join(MODES)}}}", file=sys.stderr)
        return 1
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    return MODES[argv[1]](event)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
