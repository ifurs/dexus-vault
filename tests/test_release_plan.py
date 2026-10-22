"""
scripts/release-plan.sh decides whether merging to main releases a new version.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def repo(tmp_path, version, tags=()):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "release-plan.sh", tmp_path / "scripts")
    (tmp_path / "dexus_vault").mkdir()
    (tmp_path / "dexus_vault" / "__version__.py").write_text(
        f'__version__ = "{version}"\n'
    )
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    for tag in tags:
        subprocess.run([*git, "tag", tag], check=True)
    return tmp_path


def plan(path, output=None):
    env = {"PATH": "/usr/bin:/bin"}
    if output:
        env["GITHUB_OUTPUT"] = str(output)
    return subprocess.run(
        ["bash", str(path / "scripts" / "release-plan.sh")],
        capture_output=True,
        text=True,
        env=env,
    )


def test_new_version_is_a_release(tmp_path):
    result = plan(repo(tmp_path, "0.4.1", tags=["0.3.1", "0.4.0"]))
    assert result.returncode == 0
    assert result.stdout.split() == ["version=0.4.1", "release=true"]


def test_tagged_version_is_not_a_release(tmp_path):
    result = plan(repo(tmp_path, "0.4.0", tags=["0.4.0"]))
    assert result.returncode == 0
    assert "release=false" in result.stdout


def test_first_release_without_tags(tmp_path):
    assert "release=true" in plan(repo(tmp_path, "1.0.0")).stdout


def test_version_lower_than_latest_fails(tmp_path):
    result = plan(repo(tmp_path, "0.3.9", tags=["0.4.0"]))
    assert result.returncode == 1
    assert "lower than the latest release 0.4.0" in result.stderr


def test_semver_ordering_is_numeric(tmp_path):
    # 0.10.0 sorts after 0.9.0, not before it
    assert "release=true" in plan(repo(tmp_path, "0.10.0", tags=["0.9.0"])).stdout


@pytest.mark.parametrize("version", ["0.4", "v0.4.1", "0.4.1rc1", "0.4.1; rm -rf /"])
def test_invalid_versions_fail(tmp_path, version):
    result = plan(repo(tmp_path, version))
    assert result.returncode == 1
    assert "not MAJOR.MINOR.PATCH" in result.stderr


def test_writes_github_output(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    output = tmp_path / "github_output"
    plan(repo(checkout, "0.5.0"), output)
    assert output.read_text().split() == ["version=0.5.0", "release=true"]
