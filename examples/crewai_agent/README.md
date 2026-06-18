# CrewAI Agent 示例

该目录提供基于 CrewAI 的 `RunnableAgent` 实现：`CrewAIAgent`。

使用前安装 examples 依赖并配置模型 API Key：

```bash
uv sync --group examples
export MINIMAX_API_KEY="你的 API Key"
```

`CrewAIAgent` 的接口语义：

- `invoke()`：执行 CrewAI 并返回一次完整文本结果
- `stream()`：通过 CrewAI checkpointing 文档中的事件类型监听执行过程，把 `llm_stream_chunk` / `llm_thinking_chunk` 等事件转换成 A2A 流式 `AgentResponse`


**运行**:
```bash
uv run crewai_agent/server.py
uv run crewai_agent/client.py
