from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(r"E:\AkStudio")

DEFAULT_CONFIG = {
    "roots": [str(DEFAULT_ROOT)],
    "public_repos": [
        str(DEFAULT_ROOT / "UnrealMCPServer"),
        str(DEFAULT_ROOT / "UnrealGameBuilerTool"),
        str(DEFAULT_ROOT / "UnrealEngine"),
        str(DEFAULT_ROOT / "LuaProjectViewer"),
        str(DEFAULT_ROOT / "Obsidian"),
    ],
    "project_repos": [
        str(DEFAULT_ROOT / "TheWildsGame"),
    ],
}


def appdata_config_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home()))) / "AkRepoManager"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def find_repo_root() -> Path | None:
    env_root = os.environ.get("AKSTUDIO_ROOT")
    if env_root and Path(env_root).exists():
        return Path(env_root)

    try:
        candidate = Path(__file__).resolve().parents[2]
        if (candidate / ".git").exists() or (candidate / ".akrepo" / "repos.json").exists():
            return candidate
    except IndexError:
        pass

    if DEFAULT_ROOT.exists():
        return DEFAULT_ROOT
    return None


def repo_config_path() -> Path | None:
    explicit = os.environ.get("AKREPO_CONFIG")
    if explicit:
        return Path(explicit)
    root = find_repo_root()
    if not root:
        return None
    return root / ".akrepo" / "repos.json"


def config_path() -> Path:
    repo_path = repo_config_path()
    if repo_path and repo_path.exists():
        return repo_path
    return appdata_config_path()


def _workspace_root(config_file: Path, data: dict[str, Any]) -> Path:
    workspace = data.get("workspace", {}) if isinstance(data.get("workspace"), dict) else {}
    root_value = workspace.get("root", ".")
    root = Path(root_value)
    if root.is_absolute():
        return root
    if config_file.name == "repos.json" and config_file.parent.name == ".akrepo":
        return (config_file.parent.parent / root).resolve()
    return (find_repo_root() or DEFAULT_ROOT).resolve()


def _entry_path(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("path", ""))
    return str(entry)


def _expand_paths(entries: list[Any], root: Path) -> list[str]:
    paths: list[str] = []
    for entry in entries:
        raw = _entry_path(entry)
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        normalized = str(path)
        if normalized not in paths:
            paths.append(normalized)
    return paths


def _normalize_loaded(data: dict[str, Any], source: Path) -> dict[str, Any]:
    root = _workspace_root(source, data)
    roots = data.get("roots") or [str(root)]
    normalized_roots = _expand_paths(roots, root)
    if not normalized_roots:
        normalized_roots = [str(root)]
    return {
        "roots": normalized_roots,
        "public_repos": _expand_paths(data.get("public_repos", []), root),
        "project_repos": _expand_paths(data.get("project_repos", []), root),
    }


def _relative_or_absolute(path: str, root: Path) -> str:
    target = Path(path)
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(target)


def _to_repo_config(data: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "workspace": {"name": root.name, "root": "."},
        "public_repos": [{"path": _relative_or_absolute(path, root)} for path in data.get("public_repos", [])],
        "project_repos": [{"path": _relative_or_absolute(path, root)} for path in data.get("project_repos", [])],
    }


class ConfigStore:
    def __init__(self) -> None:
        self.path = config_path()
        self.repo_root = find_repo_root() or DEFAULT_ROOT
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                data = _normalize_loaded(loaded, self.path)
            except Exception:
                data = DEFAULT_CONFIG.copy()
        else:
            data = DEFAULT_CONFIG.copy()
            self.save(data)

        for key, value in DEFAULT_CONFIG.items():
            data.setdefault(key, value.copy() if isinstance(value, list) else value)
        return data

    def save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        self.path.parent.mkdir(parents=True, exist_ok=True)
        output: dict[str, Any]
        if self.path.name == "repos.json" and self.path.parent.name == ".akrepo":
            output = _to_repo_config(self.data, self.path.parent.parent)
        else:
            output = self.data
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def add_path(self, key: str, path: str) -> None:
        normalized = str(Path(path))
        values = self.data.setdefault(key, [])
        if normalized not in values:
            values.append(normalized)
            self.save()

    def remove_path(self, key: str, path: str) -> None:
        normalized = str(Path(path))
        values = self.data.setdefault(key, [])
        self.data[key] = [item for item in values if str(Path(item)) != normalized]
        self.save()
