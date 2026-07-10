from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path

from .git_utils import RepoStatus, get_status, is_git_repo


@dataclass
class RepoNode:
    name: str
    path: str
    category: str
    url: str = ""
    branch_hint: str = ""
    status: RepoStatus | None = None
    children: list["RepoNode"] = field(default_factory=list)


CATEGORY_LABELS = {
    "root": "管理根",
    "public": "公共仓库",
    "project": "项目仓库",
    "submodule": "项目内仓库",
    "linked": "关联仓库",
    "gitmodules": ".gitmodules",
    "external": "外部依赖",
}

SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".vs",
    ".idea",
    "__pycache__",
    "Binaries",
    "Build",
    "DerivedDataCache",
    "Intermediate",
    "Saved",
    "DDC",
    "node_modules",
}


def norm(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def read_gitmodules(repo_path: str | Path) -> list[dict[str, str]]:
    modules_file = Path(repo_path) / ".gitmodules"
    if not modules_file.exists():
        return []
    parser = configparser.ConfigParser()
    parser.read(modules_file, encoding="utf-8")
    modules: list[dict[str, str]] = []
    for section in parser.sections():
        if not section.startswith("submodule"):
            continue
        name = section[len("submodule"):].strip().strip('"') or parser.get(section, "path", fallback="")
        rel_path = parser.get(section, "path", fallback="")
        url = parser.get(section, "url", fallback="")
        branch = parser.get(section, "branch", fallback="")
        if rel_path:
            modules.append({"name": name, "path": rel_path, "url": url, "branch": branch})
    return modules


def _repo_node(path: str | Path, category: str, name: str | None = None, url: str = "", branch: str = "") -> RepoNode:
    p = Path(path)
    node = RepoNode(name or p.name, str(p), category, url, branch)
    if p.exists() and is_git_repo(p):
        node.status = get_status(p)
        if not node.url and node.status.remote:
            node.url = node.status.remote
    return node


def _category(path: Path, parent_category: str, public: set[str], projects: set[str]) -> str:
    key = norm(path)
    if key in public:
        return "public"
    if key in projects:
        return "project"
    if parent_category == "root":
        return "linked"
    return "submodule"


def _find_nested_gitmodules(base: Path, excluded_roots: set[str], limit: int = 200) -> list[Path]:
    if not base.exists() or not base.is_dir():
        return []
    found: list[Path] = []
    try:
        base_norm = norm(base)
        for current, dirs, files in os.walk(base):
            current_path = Path(current)
            current_norm = norm(current_path)
            dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
            if current_norm != base_norm and any(current_norm == root or current_norm.startswith(root + os.sep) for root in excluded_roots):
                dirs[:] = []
                continue
            if ".gitmodules" in files:
                found.append(current_path)
                if len(found) >= limit:
                    break
    except OSError:
        return found
    return found


def _scan_node(
    path: str | Path,
    category: str,
    public: set[str],
    projects: set[str],
    seen: set[str],
    name: str | None = None,
    url: str = "",
    branch: str = "",
    deep_discover: bool = True,
) -> RepoNode:
    p = Path(path)
    node = _repo_node(p, category, name, url, branch)
    node_key = norm(p)
    seen.add(node_key)

    direct_child_roots: set[str] = set()
    for module in read_gitmodules(p):
        child_path = p / module["path"]
        child_key = norm(child_path)
        direct_child_roots.add(child_key)
        child_category = _category(child_path, category, public, projects)
        child = _scan_node(
            child_path,
            child_category,
            public,
            projects,
            seen,
            module["name"],
            module["url"],
            module["branch"],
            deep_discover=child_category in {"project", "submodule", "linked", "gitmodules"},
        )
        node.children.append(child)

    if deep_discover:
        for modules_owner in _find_nested_gitmodules(p, direct_child_roots):

            owner_key = norm(modules_owner)
            if owner_key == node_key or owner_key in seen:
                continue
            rel = str(modules_owner.relative_to(p)) if modules_owner.is_relative_to(p) else modules_owner.name
            discovered = _scan_node(
                modules_owner,
                "gitmodules",
                public,
                projects,
                seen,
                rel,
                "",
                "",
                deep_discover=True,
            )
            node.children.append(discovered)

    return node


def scan_config(data: dict) -> list[RepoNode]:
    public = {norm(item) for item in data.get("public_repos", [])}
    projects = {norm(item) for item in data.get("project_repos", [])}
    nodes: list[RepoNode] = []
    seen: set[str] = set()

    for root in data.get("roots", []):
        root_path = Path(root)
        if not root_path.exists():
            continue
        root_node = _scan_node(root_path, "root", public, projects, seen, deep_discover=True)

        nodes.append(root_node)

    for path in data.get("public_repos", []):
        normalized = norm(path)
        if normalized not in seen and Path(path).exists():
            nodes.append(_scan_node(path, "public", public, projects, seen, deep_discover=False))

    for path in data.get("project_repos", []):
        normalized = norm(path)
        if normalized not in seen and Path(path).exists():
            nodes.append(_scan_node(path, "project", public, projects, seen, deep_discover=True))

    return nodes


def scan_submodules(parent: RepoNode) -> list[RepoNode]:
    public: set[str] = set()
    projects: set[str] = set()
    seen: set[str] = {norm(parent.path)}
    children: list[RepoNode] = []
    parent_path = Path(parent.path)
    for module in read_gitmodules(parent_path):
        child_path = parent_path / module["path"]
        child = _scan_node(child_path, "submodule", public, projects, seen, module["name"], module["url"], module["branch"])
        children.append(child)
    return children
