#!/usr/bin/env python3
"""
Claude Code hook guards for the project agents in .claude/agents.

    guard.py bash-readonly   PreToolUse(Bash): block commands that change state
    guard.py bash-audit      like bash-readonly, plus scripts/agents/scan.sh <scan>
    guard.py tests-only      PreToolUse(Edit|Write): allow edits under tests/ only
    guard.py memory-only     PreToolUse(Edit|Write): allow edits of agent memory only
    guard.py verify          SubagentStop: block finishing while lint or tests fail

Reads the hook input JSON on stdin. Exit 2 blocks, stderr is shown to the
agent. Guards fail closed on unreadable input.

These are backstops for the agents' instructions, not a sandbox: a pattern
list cannot recognise every way a shell can change state. For untrusted
content, also run the agents with Claude Code's sandbox enabled.
"""

import json
import re
import shutil

# only fixed lint/test commands are run, without a shell
import subprocess  # nosec B404
import sys
from pathlib import Path

# commands a read-only agent must not run; `=` forms of flags are covered too
MUTATING = [
    r"\bgit\s+(commit|push|reset|checkout|switch|merge|rebase|stash|tag|clean|restore|rm|mv|add|apply|am|cherry-pick|revert|update-ref|symbolic-ref|update-index|notes|config|worktree|gc|prune|replace|filter-branch|branch\s+-[dDmMf])\b",
    r"\b(pip3?|uv|poetry|pipx|npm|apt(-get)?|brew)\s+(install|uninstall|add|remove|upgrade|pip|tool\s+install)\b",
    r"\buv\s+lock\b(?!.*\s--check\b)",
    r"(^|[\s;&|(])(rm|mv|cp|chmod|chown|touch|mkdir|rmdir|ln|truncate|dd|tee|install|rsync|shred|unlink)\s",
    r"\bsed\s+(-[a-zA-Z]*i|--in-place)",
    r"\bperl\s+-[a-zA-Z]*[ip]",
    r"\bfind\b.*\s-(delete|exec|execdir|ok|okdir|fprint\w*)\b",
    # docker as a command (the docker/tests/start.sh stack script stays allowed)
    r"(^|[\s;&|(/])(sudo\s+)?docker(?!/)(\s|$)",
    # handing a string to a shell or eval hides the real command
    r"(\|\s*|\b(env|exec|xargs|nohup|timeout|nice)\s+)(\S*/)?(ba|z|da|k)?sh\b|\b(ba|z|da|k)?sh\s+-[a-z]*c\b|\beval\b|\bsource\b|(^|[\s;&|])\.\s",
    r"\bgh\s+(pr|issue|release|repo|workflow|run|secret|variable|label|gist|cache|ruleset|attestation)\s+(create|edit|merge|close|reopen|delete|comment|review|run|set|cancel|rerun|enable|disable|upload|fork|sync|rename|archive)\b",
    # gh api sends POST as soon as a field is given; any explicit non-GET method too
    r"\bgh\s+api\b.*\s(-[fF]|--field|--raw-field|--input)([\s=]|$)",
    r"\b(gh\s+api|curl|wget|http|https)\b.*\s(-X|--method|--request)[\s=]*['\"]?(?!GET\b)[A-Za-z]",
    r"\bcurl\b.*\s(-d|--data\S*|-F|--form\S*|-T|--upload-file|--json)([\s=]|$)",
    r"\bwget\b.*\s--(post|method|body)",
    r"\b(kubectl|helm|terraform)\s+(apply|create|delete|patch|replace|install|upgrade|uninstall|destroy|import|edit|scale)\b",
    r"\baws\s+\S+\s+(put|delete|create|update|modify|remove|attach|detach|start|stop|terminate|send|invoke)-",
    r"\bvault\s+(write|delete|kv\s+(put|patch|delete|destroy|undelete|rollback)|secrets\s+(enable|disable)|auth\s+(enable|disable)|policy\s+(write|delete)|token\s+(create|revoke))\b",
    # interpreters writing files or running processes
    r"\b(python3?|node|ruby)\b.*\s-[ce]\b.*\b(open|write\w*|unlink|remove|rmtree|rename|replace|chmod|system|popen|Popen|subprocess|exec|spawn|socket|urlopen|requests)\b",
    # output redirection into a file (stderr redirects and /dev/null are fine)
    r"(^|[^0-9&>])>>?\|?\s*(?!/dev/null|&)[^\s&|;]",
    # agent memory is notes, read with the Read tool, never run or written by shell
    r"\.claude/agent-memory",
    # repository scripts that write files or run containers (scan.sh only via bash-audit)
    r"scripts/(generate_proto|agents/scan)\.sh",
    # command and process substitution hide commands from the checks above
    r"\$\(|`|<\(|>\(",
]
EDITABLE_PREFIXES = ("tests/", "docker/tests/templ/")
# project memory (shared through git) and local memory (gitignored)
MEMORY_PREFIXES = (".claude/agent-memory/", ".claude/agent-memory-local/")
# the only way the audit agent may run scanners: fixed argv in a reviewed script
SCAN_COMMAND = re.compile(
    r"(bash\s+)?(\./)?scripts/agents/scan\.sh\s+(deps|workflows|code|secrets|dockerfile|image|all)"
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
                f"(matched {pattern!r}). Run inner commands separately, or report "
                "what should be run instead."
            )
    return 0


def bash_audit(event: dict) -> int:
    command = event.get("tool_input", {}).get("command", "").strip()
    if SCAN_COMMAND.fullmatch(command):
        return 0
    return bash_readonly(event)


def _repo_root(path: Path) -> Path | None:
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _edited_path(event: dict) -> tuple[str | None, str | None]:
    """
    The repository-relative path a file tool is about to write, and the raw path.
    """
    tool_input = event.get("tool_input", {})
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None, None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or ".") / path
    path = path.resolve()
    root = _repo_root(path.parent)
    return (path.relative_to(root).as_posix() if root else None), raw


def tests_only(event: dict) -> int:
    relative, raw = _edited_path(event)
    if raw is None:
        return 0
    if relative is None or not relative.startswith(EDITABLE_PREFIXES):
        return _deny(
            f"Blocked: this agent may only edit {', '.join(EDITABLE_PREFIXES)} "
            f"(tried {raw}). Report product code bugs instead of fixing them."
        )
    return 0


def memory_only(event: dict) -> int:
    relative, raw = _edited_path(event)
    if raw is None:
        return 0
    path = Path(raw) if Path(raw).is_absolute() else Path(event.get("cwd") or ".") / raw
    # only this repository's memory, and only notes, so nothing written can be run
    same_repo = _repo_root(path.resolve().parent) == _repo_root(
        Path(event.get("cwd") or ".").resolve()
    )
    if (
        relative is None
        or not same_repo
        or not relative.startswith(MEMORY_PREFIXES)
        or not relative.endswith(".md")
    ):
        return _deny(
            f"Blocked: this agent may only write Markdown notes under "
            f"{' or '.join(MEMORY_PREFIXES)} of this repository (tried {raw}). "
            "Report changes instead of making them."
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


MODES = {
    "bash-readonly": bash_readonly,
    "bash-audit": bash_audit,
    "tests-only": tests_only,
    "memory-only": memory_only,
    "verify": verify,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in MODES:
        print(f"usage: guard.py {{{','.join(MODES)}}}", file=sys.stderr)
        return 1
    try:
        event = json.load(sys.stdin)
    except ValueError:
        if argv[1] == "verify":
            return 0
        return _deny("Blocked: the guard could not read the hook input")
    return MODES[argv[1]](event)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
