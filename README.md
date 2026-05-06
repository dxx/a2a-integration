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
| `init_server_app()` | 初始化 Starlette HTTP 应用 |
| `request_handler()` | 获取请求处理器 |

**核心抽象**:
- `RunnableAgent` - 抽象类，需实现 `invoke()` 和 `stream()` 方法

**组件**:
- `converter.py` - 请求/响应转换器
- `context.py` - 请求上下文


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
