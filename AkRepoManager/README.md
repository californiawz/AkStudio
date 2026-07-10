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

## 当前能力

- GitHub 风格浅色界面
- 自动读取 `E:\AkStudio` 以及项目内部的所有 `.gitmodules`
- 递归识别：
  - 公共仓库
  - 项目仓库
  - 项目内仓库
  - 未在父仓库直接声明、但自身存在 `.gitmodules` 的嵌套模块
- 显示路径、分支、远程、提交状态
- 搜索和按类型筛选
- 新增公共仓库配置
- 新增项目仓库配置
- 给选中的父仓库添加子仓库关联
- 对选中仓库执行：
  - `提交并推送到远端`
  - `仅本地提交`
  - `仅推送到远端`
  - `Pull`
  - `状态`
  - `更新子模块`

## 已识别的层级示例

- `AkStudio`
  - `UnrealMCPServer`
  - `UnrealGameBuilerTool`
  - `UnrealEngine`
  - `LuaProjectViewer`
  - `Obsidian`
  - `TheWildsGame`
    - `TheWildsClient`
      - `TheWilds/Plugins/KnightProtobuf`
      - `TheWilds/Plugins/SocketIOClient-Unreal`
        - `Source/ThirdParty/websocketpp`
        - `Source/ThirdParty/rapidjson`
          - `thirdparty/gtest`
        - `Source/ThirdParty/asio`
    - `TheWildsDoc`
    - `TheWildsServer`
  - `KnightGame/Knight/Plugins/SocketIOClient-Unreal`
    - `Source/ThirdParty/websocketpp`
    - `Source/ThirdParty/rapidjson`
      - `thirdparty/gtest`
    - `Source/ThirdParty/asio`

## 说明

父仓库只提交 `.gitmodules` 和 `gitlink`，不会上传子仓库目录内容。每个子仓库仍然独立提交、独立推送。
