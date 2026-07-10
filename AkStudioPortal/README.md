# AkStudio Portal

独立的 AkStudio 统一入口网页，位置：

```text
E:\AkStudio\AkStudioPortal
```

## 设计

- 参考 GitHub Dashboard 的浅色、左侧导航、卡片和工作区 Tab 风格。
- 入口统一在 Portal。
- 具体能力仍由各自模块负责，不把业务逻辑搬进 Portal。

## 集成入口

- `AkRepoManager`：整体仓库管理。
- `UnrealGameBuilerTool`：游戏项目构建发布工具。
- `LuaProjectViewer`：项目 Lua 代码阅读器。
- `Obsidian`：项目 AI 记忆库。

## 启动

```bat
E:\AkStudio\AkStudioPortal\启动AkStudio入口.bat
```

访问：

```text
http://127.0.0.1:8750
```

## 端口

- Portal：`8750`
- AkRepoManager：`8765`
- UnrealGameBuilerTool：`8766`
- LuaProjectViewer：`8770`

## 说明

Web 类型工具会在 Portal 内以内嵌 Tab 打开；Obsidian 当前作为本地目录打开。
