from __future__ import annotations

import json
import mimetypes
import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
AK_ROOT = ROOT.parent
WEB_ROOT = ROOT / "web"
OBSIDIAN_ROOT = AK_ROOT / "Obsidian"


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def apps() -> list[dict]:
    return [
        {
            "id": "repo-manager",
            "name": "AkRepoManager",
            "title": "整体仓库管理",
            "description": "管理 AkStudio、公共仓库、项目仓库和项目内子模块。",
            "path": str(AK_ROOT / "AkRepoManager"),
            "url": "http://127.0.0.1:8765",
            "port": 8765,
            "kind": "web",
            "command": [sys.executable, str(AK_ROOT / "AkRepoManager" / "web_server.py"), "8765"],
        },
        {
            "id": "builder",
            "name": "UnrealGameBuilerTool",
            "title": "游戏构建发布工具",
            "description": "构建、打包、发布 Unreal 游戏项目。处理逻辑仍在构建工具模块内。",
            "path": str(AK_ROOT / "UnrealGameBuilerTool"),
            "url": "http://127.0.0.1:8766",
            "port": 8766,
            "kind": "web",
            "command": [sys.executable, str(AK_ROOT / "UnrealGameBuilerTool" / "BuilderEntry.py"), "web", "--host", "127.0.0.1", "--port", "8766"],
        },
        {
            "id": "lua-viewer",
            "name": "LuaProjectViewer",
            "title": "Lua 代码阅读器",
            "description": "阅读、搜索、编辑项目 Lua 代码。处理逻辑仍在 LuaProjectViewer 模块内。",
            "path": str(AK_ROOT / "LuaProjectViewer"),
            "url": "http://127.0.0.1:8770",
            "port": 8770,
            "kind": "web",
            "command": [
                sys.executable,
                str(AK_ROOT / "LuaProjectViewer" / "server.py"),
                str(AK_ROOT / "TheWildsGame" / "TheWildsClient" / "Lua"),
                "8770",
            ],
        },
        {
            "id": "obsidian",
            "name": "Obsidian",
            "title": "项目 AI 记忆库",
            "description": "直接浏览项目 AI 记忆库 Markdown 笔记，内容仍由 Obsidian 仓库维护。",
            "path": str(OBSIDIAN_ROOT),
            "kind": "notes",
        },
    ]


def public_app(app: dict) -> dict:
    item = dict(app)
    path = Path(item["path"])
    item["exists"] = path.exists()
    item["running"] = bool(item.get("port") and port_open(int(item["port"])))
    item.pop("command", None)
    return item


def start_process(command: list[str], cwd: Path) -> None:
    flags = 0
    if sys.platform.startswith("win"):
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(command, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)


def launch_app(app_id: str) -> dict:
    app_map = {item["id"]: item for item in apps()}
    app = app_map.get(app_id)
    if not app:
        return {"ok": False, "error": "未知入口"}

    path = Path(app["path"])
    if not path.exists():
        return {"ok": False, "error": f"模块目录不存在，请先首次拉取: {path}"}

    if app["kind"] == "notes":
        return {"ok": True, "message": "记忆库已准备就绪"}

    if app["kind"] == "folder":
        os.startfile(str(path))
        return {"ok": True, "message": f"已打开目录: {path}"}

    port = int(app["port"])
    if not port_open(port):
        start_process(app["command"], path)
        for _ in range(25):
            if port_open(port):
                break
            time.sleep(0.2)

    return {"ok": True, "url": app["url"], "message": "入口已准备就绪"}


def safe_note_path(rel_path: str) -> Path | None:
    root = OBSIDIAN_ROOT.resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root)) or target.suffix.lower() != ".md":
        return None
    return target


def list_notes() -> list[dict]:
    if not OBSIDIAN_ROOT.exists():
        return []
    notes: list[dict] = []
    for path in OBSIDIAN_ROOT.rglob("*.md"):
        parts = set(path.relative_to(OBSIDIAN_ROOT).parts)
        if ".git" in parts or ".obsidian" in parts:
            continue
        stat = path.stat()
        rel_path = path.relative_to(OBSIDIAN_ROOT).as_posix()
        notes.append(
            {
                "path": rel_path,
                "name": path.stem,
                "folder": path.parent.relative_to(OBSIDIAN_ROOT).as_posix() if path.parent != OBSIDIAN_ROOT else "",
                "size": stat.st_size,
                "updatedAt": stat.st_mtime,
            }
        )
    return sorted(notes, key=lambda item: (item["folder"], item["name"].lower()))


def read_note(rel_path: str) -> dict:
    target = safe_note_path(rel_path)
    if not target or not target.exists() or not target.is_file():
        return {"ok": False, "error": "笔记不存在"}
    return {
        "ok": True,
        "path": target.relative_to(OBSIDIAN_ROOT).as_posix(),
        "name": target.stem,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


def save_note(rel_path: str, content: str) -> dict:
    target = safe_note_path(rel_path)
    if not target or not target.exists() or not target.is_file():
        return {"ok": False, "error": "笔记不存在"}
    target.write_text(content, encoding="utf-8", newline="")
    stat = target.stat()
    return {
        "ok": True,
        "path": target.relative_to(OBSIDIAN_ROOT).as_posix(),
        "name": target.stem,
        "size": stat.st_size,
        "updatedAt": stat.st_mtime,
    }


def json_response(handler: BaseHTTPRequestHandler, payload: dict, code: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "AkStudioPortal/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/apps":
            json_response(self, {"ok": True, "apps": [public_app(item) for item in apps()]})
            return
        if parsed.path == "/api/notes":
            json_response(self, {"ok": True, "notes": list_notes(), "root": str(OBSIDIAN_ROOT)})
            return
        if parsed.path == "/api/note":
            query = parse_qs(parsed.query)
            result = read_note((query.get("path") or [""])[0])
            json_response(self, result, 200 if result.get("ok") else 404)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") if length else "{}")
        except Exception as exc:
            json_response(self, {"ok": False, "error": f"请求解析失败: {exc}"}, 400)
            return

        if parsed.path == "/api/app/launch":
            result = launch_app(str(body.get("id", "")))
            json_response(self, result, 200 if result.get("ok") else 400)
            return
        if parsed.path == "/api/note/save":
            result = save_note(str(body.get("path", "")), str(body.get("content", "")))
            json_response(self, result, 200 if result.get("ok") else 400)
            return
        json_response(self, {"ok": False, "error": "接口不存在"}, 404)

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        target = (WEB_ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.exists() or target.is_dir():
            self.send_error(404)
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        print("[portal]", format % args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8750
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AkStudio Portal: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
