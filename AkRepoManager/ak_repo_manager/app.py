from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from .config_store import ConfigStore
    from .git_utils import add_existing_submodule, commit_all, pull, push, run_git, update_submodules
    from .repo_scanner import CATEGORY_LABELS, RepoNode, scan_config
except ImportError:
    from config_store import ConfigStore
    from git_utils import add_existing_submodule, commit_all, pull, push, run_git, update_submodules
    from repo_scanner import CATEGORY_LABELS, RepoNode, scan_config


class RepoManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AkStudio 仓库管理器")
        self.geometry("1180x760")
        self.minsize(960, 620)
        self.store = ConfigStore()
        self.nodes_by_id: dict[str, RepoNode] = {}
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.refresh_async()
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(8, 8, 8, 4))
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        buttons = [
            ("扫描", self.refresh_async),
            ("添加公共仓库", lambda: self.add_config_path("public_repos")),
            ("添加项目仓库", lambda: self.add_config_path("project_repos")),
            ("添加子仓库关联", self.add_submodule_dialog),
            ("Pull", self.pull_selected),
            ("提交", self.commit_selected),
            ("Push", self.push_selected),
            ("更新子模块", self.update_submodules_selected),
        ]
        for text, command in buttons:
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 6))

        self.tree = ttk.Treeview(
            self,
            columns=("category", "branch", "status", "url"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="仓库")
        self.tree.heading("category", text="类型")
        self.tree.heading("branch", text="分支")
        self.tree.heading("status", text="状态")
        self.tree.heading("url", text="远程")
        self.tree.column("#0", width=260)
        self.tree.column("category", width=90, anchor="center")
        self.tree.column("branch", width=120, anchor="center")
        self.tree.column("status", width=160)
        self.tree.column("url", width=420)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_details())

        right = ttk.Frame(self, padding=(4, 0, 8, 8))
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="详情 / 日志").grid(row=0, column=0, sticky="w")
        self.text = tk.Text(right, wrap="word", height=20)
        self.text.grid(row=1, column=0, sticky="nsew")
        self.text.configure(font=("Consolas", 10))

    def log(self, text: str) -> None:
        self.text.insert("end", text.rstrip() + "\n")
        self.text.see("end")

    def selected_node(self) -> RepoNode | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.nodes_by_id.get(selection[0])

    def refresh_async(self) -> None:
        self.log("开始扫描仓库关联...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            nodes = scan_config(self.store.data)
            self.queue.put(("scan_done", nodes))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "scan_done":
                    self.render_tree(payload)  # type: ignore[arg-type]
                    self.log("扫描完成。")
                elif kind == "command_done":
                    self.log(str(payload))
                    self.refresh_async()
                elif kind == "error":
                    messagebox.showerror("错误", str(payload))
                    self.log("错误：" + str(payload))
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def render_tree(self, nodes: list[RepoNode]) -> None:
        self.tree.delete(*self.tree.get_children())
        self.nodes_by_id.clear()
        for node in nodes:
            self._insert_node("", node)
        for item in self.tree.get_children():
            self.tree.item(item, open=True)

    def _insert_node(self, parent_id: str, node: RepoNode) -> str:
        branch = node.status.branch if node.status else "-"
        status = node.status.summary if node.status else "未检测到 Git"
        category = CATEGORY_LABELS.get(node.category, node.category)
        item_id = self.tree.insert(parent_id, "end", text=node.name, values=(category, branch, status, node.url))
        self.nodes_by_id[item_id] = node
        for child in node.children:
            self._insert_node(item_id, child)
        return item_id

    def show_details(self) -> None:
        node = self.selected_node()
        if not node:
            return
        self.text.delete("1.0", "end")
        self.log(f"名称: {node.name}")
        self.log(f"类型: {CATEGORY_LABELS.get(node.category, node.category)}")
        self.log(f"路径: {node.path}")
        self.log(f"远程: {node.url or '-'}")
        self.log(f"配置分支: {node.branch_hint or '-'}")
        if node.status:
            self.log(f"当前分支: {node.status.branch}")
            self.log(f"当前提交: {node.status.head}")
            self.log(f"状态: {node.status.summary}")
        self.log("\n说明：父仓库中的子仓库显示为 gitlink/submodule，只提交关联，不提交子仓库内容。")

    def add_config_path(self, key: str) -> None:
        folder = filedialog.askdirectory(title="选择仓库目录")
        if not folder:
            return
        self.store.add_path(key, folder)
        self.refresh_async()

    def add_submodule_dialog(self) -> None:
        parent = self.selected_node()
        if not parent:
            messagebox.showinfo("提示", "请先选择一个父仓库，例如 E:\\AkStudio 或 TheWildsGame。")
            return
        rel_path = simpledialog.askstring("子仓库路径", "输入相对路径，例如 TheWildsGame 或 Plugins/MyRepo：")
        if not rel_path:
            return
        default_name = Path(rel_path).name
        name = simpledialog.askstring("子仓库名称", "输入子仓库名称：", initialvalue=default_name)
        if not name:
            return
        url = simpledialog.askstring("远程地址", "输入子仓库 URL：")
        if not url:
            return
        branch = simpledialog.askstring("分支", "输入跟踪分支：", initialvalue="main") or "main"
        self._run_command(
            f"添加子仓库关联 {name}",
            lambda: add_existing_submodule(parent.path, name, rel_path, url, branch),
        )

    def _run_command(self, title: str, func) -> None:
        node = self.selected_node()
        self.log(f"开始执行：{title}")

        def worker() -> None:
            result = func()
            prefix = f"[{title}] {'成功' if result.ok else '失败'}"
            self.queue.put(("command_done", prefix + "\n" + result.text))

        threading.Thread(target=worker, daemon=True).start()

    def pull_selected(self) -> None:
        node = self.selected_node()
        if node:
            self._run_command(f"Pull {node.name}", lambda: pull(node.path))

    def push_selected(self) -> None:
        node = self.selected_node()
        if node:
            self._run_command(f"Push {node.name}", lambda: push(node.path))

    def commit_selected(self) -> None:
        node = self.selected_node()
        if not node:
            return
        message = simpledialog.askstring("提交信息", "输入 commit message：")
        if not message:
            return
        self._run_command(f"提交 {node.name}", lambda: commit_all(node.path, message))

    def update_submodules_selected(self) -> None:
        node = self.selected_node()
        if node:
            self._run_command(f"更新子模块 {node.name}", lambda: update_submodules(node.path))


if __name__ == "__main__":
    RepoManagerApp().mainloop()
