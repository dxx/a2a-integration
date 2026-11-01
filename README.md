# A2A Integration

基于 `a2a-sdk` 的 A2A (Agent-to-Agent) 协议集成实现，支持多种通信协议。


## 核心模块

```
src/
├── a2a_client/        # 客户端模块
├── a2a_server/        # 服务端模块
└── a2a_common/        # 公共组件（协议常量）
```


### a2a_common/ - 公共组件

定义协议常量和传输协议标识。

| 常量 | 说明 |
|------|------|
| `PROTOCOL_JSON_RPC` | JSON-RPC 协议 |
| `PROTOCOL_HTTP_JSON` | HTTP REST JSON 协议 |
| `PROTOCOL_GRPC` | gRPC 协议 |
| `PROTOCOL_VERSION_1_0` | 协议版本 1.0 |
| `PROTOCOL_VERSION_0_3` | 协议版本 0.3 (兼容) |


### a2a_client/ - 客户端模块

核心类 `A2AClientAgent` 用于与远程 Agent 服务通信。

**核心方法**:
| 方法 | 说明 |
|------|------|
| `get_agent_card()` | 获取 Agent 卡片信息 |
| `get_extended_agent_card()` | 获取扩展的 Agent 卡片 |
| `send_message(request, context)` | 发送普通消息 |
| `send_message_streaming(request, context)` | 发送流式消息 |

**组件**:
- `converter.py` - 请求/响应转换器
- `context.py` - 请求上下文


### a2a_server/ - 服务端模块

核心类 `A2AServerAgent` 处理来自客户端的请求。

**核心方法**:
| 方法 | 说明 |
|------|------|
| `attach_app_server(app)` | 将 A2A 路由附加到已有的 Starlette / FastAPI 应用 |
| `request_handler()` | 获取请求处理器 |
| `startup()` / `shutdown()` | 初始化 / 释放共享存储与活跃 task（幂等） |

**核心抽象**:
- `RunnableAgent` - 抽象类，需实现 `invoke()` 和 `stream()` 方法

**组件**:
- `converter.py` - 请求/响应转换器
- `context.py` - 请求上下文
- `storage.py` - 共享存储组合（task 状态 + 跨副本事件流）


## 共享存储（多副本部署）

多副本部署时，task 的状态与事件流必须放在共享存储里，否则各副本互相看不见对方的 task。

`A2AServerAgent` 通过 `shared_storage` 参数开启：

| 参数 | 说明 |
|------|------|
| `shared_storage` | 共享存储组合（task 状态 + 跨副本事件流）。默认 `None`，即进程内的 `InMemoryTaskStore`（仅单副本） |
| `interrupted_task_timeout` | 停在 `input-required` / `auth-required` 的 task 空闲多少秒后释放运行时占用；`None` 表示永不释放 |

### 怎么选 task_store

| 场景 | task_store | event_stream |
|------|-----------|--------------|
| 单进程，允许重启丢 task | `InMemoryTaskStore`（默认，不传 `shared_storage`） | 不需要 |
| 单进程，要重启不丢 / 多副本 | `DatabaseTaskStore` | 不需要 |
| 多副本，夸副本事件流 | `VersionedDatabaseTaskStore` | `DatabaseTaskEventStream` |


## 协议支持

| 协议 | 传输方式 | 版本支持 |
|------|----------|----------|
| JSON-RPC | HTTP | 1.0, 0.3 |
| REST/JSON | HTTP | 1.0, 0.3 |
| gRPC | HTTP/2 | 1.0, 0.3 |


## 设计

1. **Converter 模式** - 自定义请求/响应格式转换
2. **Context 模式** - 传递 HTTP/gRPC 元数据
3. **RunnableAgent 抽象** - 将 Agent 逻辑与 A2A 协议分离
4. **Task 状态机** - `WORKING`, `INPUT_REQUIRED`, `FAILED`, `COMPLETED`


## 示例

参考 [examples](./examples) 目录。
