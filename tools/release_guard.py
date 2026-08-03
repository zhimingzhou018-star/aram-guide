"""Git checks that must pass before a production deployment."""

from __future__ import annotations

import subprocess
from pathlib import Path


class ReleaseGateError(RuntimeError):
    """Raised when the checked-out site is not an approved release."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseGateError(f"Git 命令失败: git {' '.join(args)}\n{detail}")
    return result.stdout.strip()


def verify_production_release(
    site_dir: Path,
    approved_commit: str,
    release_tag: str,
    *,
    remote: str = "origin",
    branch: str = "main",
) -> dict[str, str]:
    """Require an exact, clean, remotely published main commit."""

    site_dir = site_dir.resolve()
    repo_root = Path(git(site_dir, "rev-parse", "--show-toplevel")).resolve()
    if repo_root != site_dir:
        raise ReleaseGateError(f"发布目录必须是 Git 仓库根目录: {repo_root}")

    current_branch = git(site_dir, "branch", "--show-current")
    if current_branch != branch:
        raise ReleaseGateError(f"正式发布只允许从 {branch} 分支执行，当前为 {current_branch or 'detached HEAD'}")

    dirty = git(site_dir, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        changed = ", ".join(line[3:] for line in dirty.splitlines()[:5])
        raise ReleaseGateError(f"工作区不干净，先提交或移除改动: {changed}")

    head = git(site_dir, "rev-parse", "HEAD")
    approved = git(site_dir, "rev-parse", f"{approved_commit}^{{commit}}")
    if approved != head:
        raise ReleaseGateError(f"验收提交不是当前 HEAD：approved={approved}，HEAD={head}")

    git(site_dir, "fetch", "--quiet", remote, branch)
    remote_head = git(site_dir, "rev-parse", f"{remote}/{branch}")
    if remote_head != head:
        raise ReleaseGateError(f"当前提交尚未同步到 {remote}/{branch}：remote={remote_head}，HEAD={head}")

    tag_commit = git(site_dir, "rev-parse", f"refs/tags/{release_tag}^{{commit}}")
    if tag_commit != head:
        raise ReleaseGateError(f"版本标签未指向当前 HEAD：tag={tag_commit}，HEAD={head}")
    remote_tags = git(
        site_dir,
        "ls-remote",
        "--tags",
        remote,
        f"refs/tags/{release_tag}",
        f"refs/tags/{release_tag}^{{}}",
    )
    remote_tag_commits = {line.split()[0] for line in remote_tags.splitlines() if line.strip()}
    if head not in remote_tag_commits:
        raise ReleaseGateError(f"版本标签尚未推送到 {remote}: {release_tag}")

    return {
        "branch": current_branch,
        "commit": head,
        "remote": f"{remote}/{branch}",
        "tag": release_tag,
    }
