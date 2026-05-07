## 示例

本目录包含 9 个子目录，展示了 A2A (Agent-to-Agent) 协议的各种实现方式。


### 目录结构

```
examples/
├── langgraph_agent/    # 核心 LangGraph Agent 实现（被其他示例引用）
├── send_message/       # 基础消息发送示例
├── jsonrpc/            # JSON-RPC over HTTP 协议
├── rest/               # HTTP+JSON REST 协议
├── grpc/               # gRPC 协议
├── hitl/               # 人工审批（Human-in-the-Loop）
├── extend_agent_card/  # 扩展 Agent Card（公开/私有技能）
├── multi/              # 多协议同时支持（JSON-RPC + REST）
└── converter/          # 自定义内容转换器
```


### 1. langgraph_agent/ - 核心模块

基础模块，提供基于 LangGraph 的 Agent 实现，被其他示例引用。

| 文件 | 作用 |
|------|------|
| `chat_model.py` | 初始化聊天模型，配置火山引擎 API |
| `agent.py` | 定义两种 Agent：`LangGraphAgent`(返回结构化数据) 和 `SimpleLangGraphAgent`(返回字符串) |
| `agent_hitl.py` | 支持 Human-in-the-Loop (HITL) 人工审批功能的 Agent |

**主要功能**:
- 集成 LangChain/LangGraph 框架
- 支持流式输出 (`stream`)
- 支持工具调用 (`read_file`, `write_file`)
- HITL 模式下可对危险操作进行人工审批

**查看 `langgraph_agent/chat_model.py`, 配置好 `BASE_URL` 和 `API_KEY`**。


### 2. send_message/ - 基础消息发送示例

展示基本的 `send_message` 和 `send_message_streaming` 用法。

**运行**:
```bash
uv run send_message/server.py
uv run send_message/client.py
```

**主要功能**:
- `send_message()` 同步调用，返回完整响应
- `send_message_streaming()` 流式调用，异步响应
- 最基础的 A2A 通信示例


### 3. jsonrpc/ - JSON-RPC 协议示例

基于 JSON-RPC over HTTP 的 A2A 服务实现。

**运行**:
```bash
uv run jsonrpc/server.py
uv run jsonrpc/client.py
```

**特点**:
- 多协议版本 (1.0 和 0.3)
- 暴露 `/a2a/jsonrpc` 端点
- 使用 `RequestContext` 传递 metadata 和 header 参数


### 4. rest/ - REST 协议示例

基于 HTTP+JSON REST 接口的 A2A 服务实现。

**运行**:
```bash
uv run rest/server.py
uv run rest/client.py
```

**特点**:
- 多协议版本 (1.0 和 0.3)
- 暴露 `/a2a/rest` 端点
- 使用 `RequestContext` 传递 metadata 和 header 参数


### 5. grpc/ - gRPC 协议示例

基于 gRPC 的 A2A 服务实现，同时支持 HTTP 服务。

**运行**:
```bash
uv run grpc/server.py
uv run grpc/client.py
```

**特点**:
- gRPC 服务端口: 18080
- 兼容版本端口: 18081
- HTTP 服务端口: 8080


### 6. hitl/ - 人工审批示例

展示如何实现 Human-in-the-Loop (HITL) 人工审批机制。

**运行**:
```bash
uv run hitl/server.py
uv run hitl/client.py
```

**主要功能**:
- Agent 可在执行危险操作前中断，等待人工审批
- 客户端收到中断后可以输入 `approve` 或 `reject` 决定是否继续
- 使用 `interrupt_id` 和 `interrupt` 跟踪中断状态


### 7. extend_agent_card/ - 扩展 Agent Card 示例

展示 A2A 协议的扩展 Agent Card 功能，支持公开/私有技能分离。

**运行**:
```bash
uv run extend_agent_card/server.py
uv run extend_agent_card/client.py
```

**主要功能**:
- `extended_agent_card=True` 开启扩展功能
- 公开技能：认证前可用
- 扩展技能：认证后才可用
- 客户端可调用 `get_extended_agent_card()` 获取扩展 Agent Card


### 8. multi/ - 多协议示例

展示同时支持 JSON-RPC 和 REST 两种协议的服务端和客户端。

**运行**:
```bash
uv run multi/server.py
uv run multi/client_rest.py   # REST 客户端
uv run multi/client_jsonrpc.py  # JSON-RPC 客户端
```

**特点**:
- 服务端同时暴露 `/a2a/jsonrpc` 和 `/a2a/rest` 端点
- 提供两个客户端示例分别使用 REST 和 JSON-RPC 协议


### 9. converter/ - 自定义内容转换器示例

演示如何自定义 A2A 协议中请求/响应的 part 转换器。

**运行**:
```bash
uv run converter/server.py
uv run converter/client.py
```

**主要功能**:
- `CustomRequestPartConverter` 自定义请求转换器
- `CustomResponsePartConverter` 自定义响应转换器
- 提供 `server_hitl.py` 和 `client_hitl.py` 支持 HITL 版本


### 共同特点

- 所有服务端都使用 `A2AServerAgent` 作为核心
- 所有客户端都使用 `A2AClientAgent` 与 Agent 通信
- 支持流式响应 (streaming)
- 支持 0.3 和 1.0 双版本协议兼容

### Agent Card 端点

服务端启动后访问: `http://127.0.0.1:8080/.well-known/agent-card.json`
