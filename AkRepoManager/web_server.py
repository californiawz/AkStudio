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
from urllib.parse import urlparse


from ak_repo_manager.config_store import ConfigStore
from ak_repo_manager.git_utils import add_existing_submodule, commit_all, commit_and_push, init_submodules, pull, push, run_git, update_submodules


from ak_repo_manager.repo_scanner import CATEGORY_LABELS, RepoNode, scan_config

ROOT = Path(__file__).resolve().parent
AK_ROOT = ROOT.parent
WEB_ROOT = ROOT / "web"





def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _tool_apps() -> list[dict]:
    return [
        {
            "id": "repo-manager",
            "name": "AkRepoManager",
            "title": "整体仓库管理",
            "description": "统一管理 AkStudio、公共仓库、项目仓库和项目内子模块。",
            "path": str(ROOT),
            "type": "web",
            "url": "http://127.0.0.1:8765",
            "port": 8765,
            "entry": "web_server.py",
        },
        {
            "id": "builder",
            "name": "UnrealGameBuilerTool",
            "title": "游戏构建发布工具",
            "description": "由构建工具模块处理 Unreal 项目构建、打包、发布。",
            "path": str(AK_ROOT / "UnrealGameBuilerTool"),
            "type": "web-service",
            "url": "http://127.0.0.1:8766",
            "port": 8766,
            "entry": "BuilderEntry.py",
        },
        {
            "id": "lua-viewer",
            "name": "LuaProjectViewer",
            "title": "Lua 代码阅读器",
            "description": "由 LuaProjectViewer 模块处理 Lua 文件树、搜索、阅读和编辑。",
            "path": str(AK_ROOT / "LuaProjectViewer"),
            "type": "web-service",
            "url": "http://127.0.0.1:8770",
            "port": 8770,
            "entry": "server.py",
            "defaultArg": str(AK_ROOT / "TheWildsGame" / "TheWildsClient" / "Lua"),
        },
        {
            "id": "obsidian",
            "name": "Obsidian",
            "title": "项目 AI 记忆库",
            "description": "打开 Obsidian 记忆库目录，AI 记忆内容仍由 Obsidian 仓库管理。",
            "path": str(AK_ROOT / "Obsidian"),
            "type": "folder",
        },
    ]


def _public_app(app: dict) -> dict:
    item = dict(app)
    path = Path(item.get("path", ""))
    port = item.get("port")
    item["exists"] = path.exists()
    item["running"] = bool(port and _port_open(int(port)))
    return item


def _open_url(url: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(url)


def _start_process(args: list[str], cwd: Path) -> None:
    flags = 0
    if sys.platform.startswith("win"):
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)


def launch_app(app_id: str) -> dict:
    apps = {app["id"]: app for app in _tool_apps()}
    app = apps.get(app_id)
    if not app:
        return {"ok": False, "error": "未知工具入口"}

    path = Path(app["path"])
    if not path.exists():
        return {"ok": False, "error": f"模块目录不存在，请先首次拉取: {path}"}

    if app["type"] == "folder":
        os.startfile(str(path))
        return {"ok": True, "message": f"已打开目录: {path}"}

    url = app.get("url", "")
    port = app.get("port")
    if port and _port_open(int(port)):
        _open_url(url)
        return {"ok": True, "url": url, "message": "服务已运行，已打开入口。"}

    if app_id == "repo-manager":
        _open_url(url)
        return {"ok": True, "url": url, "message": "已打开仓库管理入口。"}

    if app_id == "builder":
        entry = path / "BuilderEntry.py"
        if not entry.exists():
            return {"ok": False, "error": f"入口文件不存在，请先首次拉取: {entry}"}
        _start_process([sys.executable, str(entry), "web", "--host", "127.0.0.1", "--port", str(port)], path)
    elif app_id == "lua-viewer":
        entry = path / "server.py"
        if not entry.exists():
            return {"ok": False, "error": f"入口文件不存在，请先首次拉取: {entry}"}
        args = [sys.executable, str(entry)]
        default_arg = app.get("defaultArg")
        if default_arg and Path(default_arg).exists():
            args += [default_arg, str(port)]
        else:
            args += [str(path), str(port)]
        _start_process(args, path)


    for _ in range(20):
        if port and _port_open(int(port)):
            _open_url(url)
            return {"ok": True, "url": url, "message": "服务已启动，已打开入口。"}
        time.sleep(0.2)
    return {"ok": True, "url": url, "message": "已尝试启动服务，如未自动打开请稍后手动访问。"}



def node_to_dict(node: RepoNode) -> dict:

    status = node.status
    return {
        "name": node.name,
        "path": node.path,
        "category": node.category,
        "categoryLabel": CATEGORY_LABELS.get(node.category, node.category),
        "url": node.url,
        "branchHint": node.branch_hint,
        "status": None if not status else {
            "branch": status.branch,
            "head": status.head,
            "remote": status.remote,
            "dirty": status.dirty,
            "aheadBehind": status.ahead_behind,
            "summary": status.summary,
        },
        "children": [node_to_dict(child) for child in node.children],
    }


def json_response(handler: BaseHTTPRequestHandler, payload: dict, code: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "AkRepoManager/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            self.handle_scan()
            return
        if parsed.path == "/api/apps":
            self.handle_apps()
            return
        self.serve_static(parsed.path)


    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            body = json.loads(raw or "{}")
        except Exception as exc:
            json_response(self, {"ok": False, "error": f"请求解析失败: {exc}"}, 400)
            return

        if parsed.path == "/api/config/path":
            self.handle_config_path(body)
        elif parsed.path == "/api/submodule":
            self.handle_submodule(body)
        elif parsed.path == "/api/action":
            self.handle_action(body)
        elif parsed.path == "/api/app/launch":
            self.handle_app_launch(body)
        else:

            json_response(self, {"ok": False, "error": "接口不存在"}, 404)

    def handle_scan(self) -> None:
        store = ConfigStore()
        nodes = scan_config(store.data)
        json_response(self, {"ok": True, "config": store.data, "nodes": [node_to_dict(node) for node in nodes]})

    def handle_apps(self) -> None:
        json_response(self, {"ok": True, "apps": [_public_app(app) for app in _tool_apps()]})

    def handle_app_launch(self, body: dict) -> None:
        result = launch_app(str(body.get("id", "")))
        json_response(self, result, 200 if result.get("ok") else 400)

    def handle_config_path(self, body: dict) -> None:

        key = body.get("key")
        path = body.get("path")
        if key not in {"public_repos", "project_repos", "roots"} or not path:
            json_response(self, {"ok": False, "error": "参数错误"}, 400)
            return
        store = ConfigStore()
        store.add_path(key, path)
        json_response(self, {"ok": True})

    def handle_submodule(self, body: dict) -> None:
        required = ["parentPath", "name", "relPath", "url"]
        if any(not body.get(key) for key in required):
            json_response(self, {"ok": False, "error": "缺少必要参数"}, 400)
            return
        result = add_existing_submodule(
            body["parentPath"],
            body["name"],
            body["relPath"],
            body["url"],
            body.get("branch") or "main",
        )
        json_response(self, {"ok": result.ok, "output": result.text, "code": result.code}, 200 if result.ok else 500)

    def handle_action(self, body: dict) -> None:
        action = body.get("action")
        path = body.get("path")
        if not path:
            json_response(self, {"ok": False, "error": "缺少仓库路径"}, 400)
            return
        if action == "open_folder":
            target = Path(path)
            if not target.exists():
                json_response(self, {"ok": False, "error": f"目录不存在: {path}"}, 404)
                return
            os.startfile(str(target))
            json_response(self, {"ok": True, "output": f"已打开目录: {path}", "code": 0})
            return
        if action == "pull":
            result = pull(path)

        elif action == "push":
            result = push(path)
        elif action == "commit":
            message = body.get("message") or "Update repository"
            result = commit_all(path, message)
        elif action == "commit_push":
            message = body.get("message") or "Update repository"
            result = commit_and_push(path, message)
        elif action == "update_submodules":

            result = update_submodules(path)
        elif action == "init_recommended":
            result = init_submodules(path, include_unreal_engine=False)
        elif action == "init_all" or action == "init_selected":
            result = init_submodules(path, include_unreal_engine=True)
        elif action == "status":

            result = run_git(path, ["status", "--short", "--branch"])
        else:
            json_response(self, {"ok": False, "error": "未知操作"}, 400)
            return
        json_response(self, {"ok": result.ok, "output": result.text, "code": result.code}, 200 if result.ok else 500)

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
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


    def log_message(self, format: str, *args) -> None:
        print("[web]", format % args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AkStudio 仓库管理器: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
