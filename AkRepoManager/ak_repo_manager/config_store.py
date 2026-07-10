from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "roots": [r"E:\AkStudio"],
    "public_repos": [
        r"E:\AkStudio\UnrealMCPServer",
        r"E:\AkStudio\UnrealGameBuilerTool",
        r"E:\AkStudio\UnrealEngine",
        r"E:\AkStudio\LuaProjectViewer",
        r"E:\AkStudio\Obsidian",
    ],

    "project_repos": [
        r"E:\AkStudio\TheWildsGame",
    ],
}


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home()))) / "AkRepoManager"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


class ConfigStore:
    def __init__(self) -> None:
        self.path = config_path()
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.save(DEFAULT_CONFIG.copy())
            return DEFAULT_CONFIG.copy()
        try:
            with self.path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
        except Exception:
            loaded = DEFAULT_CONFIG.copy()
        for key, value in DEFAULT_CONFIG.items():
            loaded.setdefault(key, value.copy() if isinstance(value, list) else value)
        return loaded

    def save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

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
