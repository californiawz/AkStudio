# AkStudio 游戏仓库管理系统

位置：`E:\AkStudio\AkRepoManager`

## 启动

推荐双击：

```bat
E:\AkStudio\AkRepoManager\启动仓库管理器.bat
```

启动后访问：

```text
http://127.0.0.1:8765
```

## 配置同步设计

配置已放到 AkStudio 父仓库中：

```text
E:\AkStudio\.akrepo\repos.json
```

这个文件会提交到：

```text
https://github.com/californiawz/AkStudio.git
```

设计原则：

- `.gitmodules`：负责 Git 子模块真实关联，包含 `path`、`url`、`branch`
- `.akrepo/repos.json`：负责管理器分类配置，区分公共仓库、项目仓库
- 配置使用相对路径，例如 `TheWildsGame`，新电脑不强绑定旧机器绝对路径
- 管理器启动时优先读取 `.akrepo/repos.json`
- 如果 `.akrepo/repos.json` 不存在，才使用本机 `%APPDATA%` 的临时配置

## 新电脑使用流程

```bat
git clone https://github.com/californiawz/AkStudio.git E:\AkStudio
cd /d E:\AkStudio
git submodule update --init --recursive
```

然后启动管理器，它会从：

```text
E:\AkStudio\.akrepo\repos.json
```

自动识别公共仓库和项目仓库。

## 当前能力

- GitHub 风格浅色界面
- 自动读取 `E:\AkStudio` 以及项目内部的所有 `.gitmodules`
- 递归识别公共仓库、项目仓库、项目内仓库和嵌套模块
- 显示路径、父仓库、分支、远程、提交状态
- 搜索、筛选、折叠/展开
- 打开选中仓库目录
- 集中首次拉取：
  - `首次拉取推荐`：拉取公共仓库和项目仓库，默认跳过超大的 `UnrealEngine`
  - `首次拉取全部`：包含 `UnrealEngine`
  - `首次拉取该仓库及子模块`：只初始化当前选中的仓库
- 新增公共仓库配置

- 新增项目仓库配置
- 给选中的父仓库添加子仓库关联
- 对选中仓库执行：`提交并推送到远端`、`仅本地提交`、`仅推送到远端`、`Pull`、`状态`、`更新子模块`

## 说明

父仓库只提交 `.gitmodules`、`.akrepo/repos.json` 和 `gitlink`，不会上传子仓库目录内容。每个子仓库仍然独立提交、独立推送。
