import os
from typing import Any, AsyncIterator
from datetime import datetime

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelSettings,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from openai.types import chat

from a2a_server import AgentRequest, AgentResponse, RequestContext, RunnableAgent


BASE_URL = "https://api.minimaxi.com/v1"
API_KEY = os.getenv("MINIMAX_API_KEY")


class MiniMaxOpenAIChatModel(OpenAIChatModel):
    """兼容 MiniMax OpenAI-compatible 响应中的非标准字段。"""

    def _validate_completion(self, response: chat.ChatCompletion) -> chat.ChatCompletion:
        data = response.model_dump()
        if data.get("service_tier") == "standard":
            data.pop("service_tier", None)
        return chat.ChatCompletion.model_validate(data)


class PydanticAIAgent(RunnableAgent):
    """基于 Pydantic AI 的 Agent 实现。返回 str 类型的数据。"""

    def __init__(self) -> None:
        model = MiniMaxOpenAIChatModel(
            "MiniMax-M3",
            provider=OpenAIProvider(
                base_url=BASE_URL,
                api_key=API_KEY,
            ),
            settings=ModelSettings(
                # Minimax 将思考字段从 content 中分离出来。
                extra_body={"reasoning_split": True},
            ),
        )
        agent = Agent(
            model,
            output_type=str,
            system_prompt=(
                "你是一个通过 A2A 协议对外提供能力的 Pydantic AI Agent。"
                "请准确理解用户问题，并给出清晰、可执行的回答。"
            ),
        )
        
        @agent.tool_plain(name="get_current_time")
        async def get_current_time() -> str:
            """获取当前本地时间。"""
            return datetime.now().astimezone().isoformat(timespec="seconds")

        self._agent = agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        query = self._get_query(request)
        output = await self._agent.run(
            self._build_prompt(query, request.context_id)
        )
    
        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=output.output,
        )

    async def stream(
        self, request: AgentRequest, context: RequestContext
    ) -> AsyncIterator[AgentResponse]:
        query = self._get_query(request)
        async for event in self._agent.run_stream_events(
            self._build_prompt(query, request.context_id)
        ):
            content = self._event_to_text(event)
            if content:
                yield AgentResponse(
                    is_complete=False,
                    require_input=False,
                    content=content,
                )

        yield AgentResponse(
            is_complete=True,
            require_input=False,
            content=None,
        )

    def _get_query(self, request: AgentRequest) -> str:
        if isinstance(request.content, str):
            query = request.content.strip()
            if query:
                return query

        raise ValueError("Content is invalid")

    def _build_prompt(self, query: str, context_id: str) -> str:
        return f"对话上下文 ID：{context_id}\n用户问题：{query}"

    def _event_to_text(self, event: Any) -> str | None:
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, TextPart | ThinkingPart):
                return event.part.content

        if isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                return event.delta.content_delta
            if isinstance(event.delta, ThinkingPartDelta):
                return event.delta.content_delta
            if isinstance(event.delta, ToolCallPartDelta):
                return None

        if isinstance(event, FunctionToolCallEvent):
            return f"Calling tools {event.part.tool_name}"

        if isinstance(event, FunctionToolResultEvent):
            tool_name = getattr(event.result, "tool_name", None) or "unknown"
            content = event.content or getattr(event.result, "content", "")
            return f"Tool {tool_name} response {content}"

        if isinstance(event, AgentRunResultEvent):
            return None

        return None
