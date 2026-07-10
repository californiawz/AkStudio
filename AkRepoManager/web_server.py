from __future__ import annotations

import json
import mimetypes
import os
import sys

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ak_repo_manager.config_store import ConfigStore
from ak_repo_manager.git_utils import add_existing_submodule, commit_all, commit_and_push, pull, push, run_git, update_submodules

from ak_repo_manager.repo_scanner import CATEGORY_LABELS, RepoNode, scan_config

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


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
        else:
            json_response(self, {"ok": False, "error": "接口不存在"}, 404)

    def handle_scan(self) -> None:
        store = ConfigStore()
        nodes = scan_config(store.data)
        json_response(self, {"ok": True, "config": store.data, "nodes": [node_to_dict(node) for node in nodes]})

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
