from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitResult:
    ok: bool
    stdout: str
    stderr: str
    code: int

    @property
    def text(self) -> str:
        return (self.stdout + ("\n" if self.stdout and self.stderr else "") + self.stderr).strip()


@dataclass
class RepoStatus:
    path: str
    branch: str
    head: str
    remote: str
    dirty: bool
    ahead_behind: str
    summary: str


def find_git() -> str:
    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    found = shutil.which("git.exe") or shutil.which("git")
    return found or "git"


GIT = find_git()


def run_git(repo_path: str | Path, args: list[str], timeout: int = 180) -> GitResult:
    repo = str(repo_path)
    try:
        completed = subprocess.run(
            [GIT, *args],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return GitResult(completed.returncode == 0, completed.stdout, completed.stderr, completed.returncode)
    except Exception as exc:
        return GitResult(False, "", str(exc), -1)


def is_git_repo(path: str | Path) -> bool:
    p = Path(path)
    return (p / ".git").exists() or run_git(p, ["rev-parse", "--is-inside-work-tree"], 20).ok


def get_one(repo_path: str | Path, args: list[str], default: str = "") -> str:
    result = run_git(repo_path, args, 60)
    if not result.ok:
        return default
    return result.stdout.strip() or default


def get_status(repo_path: str | Path) -> RepoStatus:
    path = str(Path(repo_path))
    branch = get_one(path, ["rev-parse", "--abbrev-ref", "HEAD"], "-")
    head = get_one(path, ["rev-parse", "--short", "HEAD"], "-")
    remote = get_one(path, ["config", "--get", "remote.origin.url"], "")
    status = run_git(path, ["status", "--porcelain=v1", "--branch", "-uno"], 120)
    lines = status.stdout.splitlines() if status.ok else []
    first = lines[0] if lines else ""
    dirty = any(line and not line.startswith("##") for line in lines)
    ahead_behind = ""
    if "[" in first and "]" in first:
        ahead_behind = first[first.find("[") + 1:first.rfind("]")]
    summary = "干净" if not dirty else f"有变更 {sum(1 for line in lines if line and not line.startswith('##'))} 项"
    if ahead_behind:
        summary += f"，{ahead_behind}"
    return RepoStatus(path, branch, head, remote, dirty, ahead_behind, summary)


def commit_all(repo_path: str | Path, message: str) -> GitResult:
    add = run_git(repo_path, ["add", "-A"], 300)
    if not add.ok:
        return add
    return run_git(repo_path, ["commit", "-m", message], 300)


def push(repo_path: str | Path) -> GitResult:
    result = run_git(repo_path, ["push"], 600)
    if result.ok:
        return result
    text = result.text.lower()
    branch = get_one(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"], "")
    if branch and branch not in {"HEAD", "-"} and ("no upstream" in text or "upstream branch" in text):
        return run_git(repo_path, ["push", "-u", "origin", branch], 600)
    return result


def commit_and_push(repo_path: str | Path, message: str) -> GitResult:
    changes = run_git(repo_path, ["status", "--porcelain=v1"], 120)
    if not changes.ok:
        return changes

    outputs: list[str] = []
    if changes.stdout.strip():
        commit = commit_all(repo_path, message)
        outputs.append(commit.text or "本地提交完成。")
        if not commit.ok:
            return GitResult(False, "\n\n".join(outputs), "", commit.code)
    else:
        outputs.append("工作区没有本地变更，跳过本地提交。")

    pushed = push(repo_path)
    outputs.append(pushed.text or "已推送到远端。")
    return GitResult(pushed.ok, "\n\n".join(outputs), "", pushed.code)


def pull(repo_path: str | Path) -> GitResult:

    return run_git(repo_path, ["pull", "--ff-only"], 600)


def update_submodules(repo_path: str | Path) -> GitResult:
    return run_git(repo_path, ["submodule", "update", "--init", "--recursive"], 1200)


def _submodule_paths(repo_path: str | Path) -> list[str]:
    modules_file = Path(repo_path) / ".gitmodules"
    if not modules_file.exists():
        return []
    result = run_git(repo_path, ["config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    if not result.ok:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            paths.append(parts[1].strip())
    return paths


def init_submodules(repo_path: str | Path, include_unreal_engine: bool = True) -> GitResult:
    paths = _submodule_paths(repo_path)
    if not paths:
        return GitResult(True, "当前仓库没有 .gitmodules，无需首次拉取。", "", 0)

    selected_paths = paths
    if not include_unreal_engine:
        selected_paths = [path for path in paths if path.replace("\\", "/").lower() != "unrealengine"]

    if not selected_paths:
        return GitResult(True, "没有需要拉取的子模块。", "", 0)

    command = ["submodule", "update", "--init", "--recursive", "--", *selected_paths]
    result = run_git(repo_path, command, 7200)
    title = "首次拉取完成。" if result.ok else "首次拉取失败。"
    skipped = "\n已跳过 UnrealEngine。" if not include_unreal_engine and "UnrealEngine" in paths else ""
    stdout = title + skipped + "\n\n" + (result.text or "无输出。")
    return GitResult(result.ok, stdout, "", result.code)


def add_existing_submodule(parent_path: str | Path, name: str, rel_path: str, url: str, branch: str = "main") -> GitResult:

    parent = Path(parent_path)
    target = parent / rel_path
    if target.exists() and is_git_repo(target):
        commands = [
            ["config", "-f", ".gitmodules", f"submodule.{name}.path", rel_path],
            ["config", "-f", ".gitmodules", f"submodule.{name}.url", url],
        ]
        if branch:
            commands.append(["config", "-f", ".gitmodules", f"submodule.{name}.branch", branch])
        output: list[str] = []
        for command in commands:
            result = run_git(parent, command)
            output.append(result.text)
            if not result.ok:
                return result
        add = run_git(parent, ["add", "-f", ".gitmodules", rel_path], 300)
        return GitResult(add.ok, "\n".join(filter(None, output + [add.stdout])), add.stderr, add.code)
    command = ["submodule", "add"]
    if branch:
        command += ["-b", branch]
    command += [url, rel_path]
    return run_git(parent, command, 1200)
