import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import Any, AsyncIterator

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool
from crewai.state.checkpoint_config import CheckpointConfig
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.llm_events import LLMStreamChunkEvent, LLMThinkingChunkEvent
from crewai.events.types.tool_usage_events import ToolUsageFinishedEvent

from a2a_server import AgentRequest, AgentResponse, RequestContext, RunnableAgent


BASE_URL = "https://api.minimaxi.com/v1"
API_KEY = os.getenv("MINIMAX_API_KEY")

class CrewAIAgent(RunnableAgent):
    """基于 CrewAI 的 Agent 实现。返回 str 类型的数据。"""

    def __init__(self, checkpoint_location: str = "./.checkpoints/crewai") -> None:
        self._checkpoint_location = checkpoint_location

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        query = self._get_query(request)
        crew = self._create_crew(stream=False)
        output = await crew.kickoff_async(
            inputs={"query": query, "context_id": request.context_id}
        )

        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=self._output_to_text(output),
        )

    async def stream(
        self, request: AgentRequest, context: RequestContext
    ) -> AsyncIterator[AgentResponse]:
        query = self._get_query(request)
        queue: asyncio.Queue[str] = asyncio.Queue()
        yielded_content = False

        with crewai_event_bus.scoped_handlers():
            self._register_stream_handlers(queue)

            run_task = asyncio.create_task(
                self._run_streaming_crew(query, request.context_id)
            )

            while not run_task.done() or not queue.empty():
                try:
                    content = await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                if content or content != "{}":
                    yielded_content = True
                    yield AgentResponse(
                        is_complete=False,
                        require_input=False,
                        content=content,
                    )

            output = await run_task

        if not yielded_content:
            fallback = self._output_to_text(output)
            if fallback:
                yield AgentResponse(
                    is_complete=False,
                    require_input=False,
                    content=fallback,
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

    def _create_crew(self, stream: bool) -> Crew:
        llm = LLM(
            model="MiniMax-M3",
            provider="openai",
            base_url=BASE_URL,
            api_key=API_KEY,
            stream=stream,
            additional_params={
                # Minimax 将思考字段从 content 中分离出来。
                "extra_body": {"reasoning_split": True},
            },
        )
        assistant = Agent(
            role="通用 AI 助手",
            goal="准确理解用户问题，并给出清晰、可执行的回答。",
            backstory="你是一个通过 A2A 协议对外提供能力的 CrewAI Agent。",
            llm=llm,
            tools=[self._create_context_tool()],
            verbose=True,
        )
        task = Task(
            description=(
                "对话上下文 ID：{context_id}\n"
                "用户问题：{query}\n\n"
                "请直接回答用户问题。需要获取当前时间时，可以调用 get_current_time 工具。"
            ),
            expected_output="一段清晰、准确、可以直接展示给用户的回答。",
            agent=assistant,
        )

        checkpoint = CheckpointConfig(
            location=str(Path(self._checkpoint_location)),
            on_events=[
                "llm_stream_chunk",
                "llm_thinking_chunk",
                "tool_usage_finished",
            ],
            max_checkpoints=20,
        )
        return Crew(
            agents=[assistant],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
            checkpoint=checkpoint,
        )

    async def _run_streaming_crew(self, query: str, context_id: str) -> Any:
        crew = self._create_crew(stream=True)
        return await crew.kickoff_async(
            inputs={"query": query, "context_id": context_id}
        )

    def _create_context_tool(self):
        @tool("get_current_time")
        async def get_current_time() -> str:
            """获取当前本地时间。"""
            return datetime.now().astimezone().isoformat(timespec="seconds")

        return get_current_time

    def _register_stream_handlers(self, queue: asyncio.Queue[str]) -> None:

        @crewai_event_bus.on(LLMThinkingChunkEvent)
        def on_llm_thinking(
            _source: Any, event: LLMThinkingChunkEvent
        ) -> None:
            if event.chunk:
                queue.put_nowait(event.chunk)

        @crewai_event_bus.on(LLMStreamChunkEvent)
        def on_llm_stream(_source: Any, event: LLMStreamChunkEvent) -> None:
            if event.chunk:
                queue.put_nowait(event.chunk)
            if event.tool_call:
                queue.put_nowait(self._tool_call_to_text(event.tool_call))

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def on_tool_finished(
            source: Any, event: ToolUsageFinishedEvent
        ) -> None:
            tool_name = self._source_name(source)
            queue.put_nowait(f"Tool {tool_name} response {event.output}")

    def _tool_call_to_text(self, tool_call: Any) -> str:
        function = getattr(tool_call, "function", None)
        name = getattr(function, "name", None) or "unknown"

        return f"Calling tools {name}"

    def _source_name(self, source: Any) -> str:
        return (
            getattr(source, "name", None)
            or getattr(source, "tool_name", None)
            or source.__class__.__name__
        )

    def _output_to_text(self, output: Any) -> str:
        raw = getattr(output, "raw", None)
        if raw:
            return str(raw)

        return str(output)
