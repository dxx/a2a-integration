# Pydantic AI Agent 示例

该目录提供基于 Pydantic AI 的 `RunnableAgent` 实现：`PydanticAIAgent`。

使用前安装 examples 依赖并配置模型 API Key：

```bash
uv sync --group examples
export MINIMAX_API_KEY="你的 API Key"
```

`PydanticAIAgent` 的接口语义：

- `invoke()`：调用 Pydantic AI Agent，返回完整文本结果
- `stream()`：使用 `run_stream_events()` 输出文本增量，并把工具事件转换成 `Calling tools ...` / `Tool ... response ...`


**运行**:
```bash
uv run _agent/server.py
uv run crewai_agent/client.py
