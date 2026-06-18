
from datetime import datetime
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk
from langchain_core.tools import tool
from typing import AsyncIterator, Literal
from dataclasses import dataclass, asdict 

from a2a_server import RunnableAgent, AgentRequest, AgentResponse, RequestContext
from examples.langgraph_agent.chat_model import get_chat_model

@dataclass
class AgentData:
    """Agent 数据"""

    type: Literal["ai", "tool"]
    """类型"""

    text: str
    """文本内容"""

    name: str | None = None
    """可选的名称"""

    tool_calls: list[str] | None = None
    """工具调用名称"""


class LangGraphAgent(RunnableAgent):
    """基于 LangGraph 的 Agent 实现。返回 AgentData 类型的数据"""

    def __init__(self):
        model = get_chat_model()

        @tool
        async def get_current_time() -> str:
            """获取当前本地时间。"""
            return datetime.now().astimezone().isoformat(timespec="seconds")
        
        langchain_agent = create_agent(
            model=model,
            tools=[get_current_time]
        )

        self._agent = langchain_agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        output = await self._agent.ainvoke(
            inputs,  # type: ignore[arg-type]
            config
        )

        latest_message = output["messages"][-1]

        data = AgentData(
            type="ai",
            name=latest_message.name if latest_message.name else "",
            text=latest_message.text,
            tool_calls=[tc["name"] for tc in (latest_message.tool_calls or [])]
        )
        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=asdict(data),
        )

    async def stream(self, request: AgentRequest, context: RequestContext) -> AsyncIterator[AgentResponse]:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")

        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        async for item in self._agent.astream(
            inputs,  # type: ignore[arg-type]
            config, stream_mode="values"
        ):
            # 获取最后的消息
            latest_message = item["messages"][-1]

            if isinstance(latest_message, AIMessage):
                text = ""
                tool_calls = []
                if latest_message.text:
                    text = latest_message.text
                    print(f"Agent: {text}")
  
                if latest_message.tool_calls:
                    tool_names = [tc["name"] for tc in latest_message.tool_calls]
                    tool_call = "、".join(tool_names)
                    
                    print(f"Calling tools: {tool_call}")

                    tool_calls = tool_names

                data = AgentData(
                    type="ai",
                    name=latest_message.name if latest_message.name else "",
                    text=text,
                    tool_calls=tool_calls
                )
                yield AgentResponse(
                    is_complete=False,
                    require_input=False,
                    content=asdict(data)
                )
            elif isinstance(latest_message, ToolMessage):
                tool_name = latest_message.name
                tool_response = latest_message.text

                print(f"Tool {tool_name} response {tool_response}")

                data = AgentData(
                    type="tool",
                    name=tool_name if tool_name else "",
                    text=tool_response,
                    tool_calls=[]
                )
                yield AgentResponse(
                    is_complete=False,
                    require_input=False,
                    content=asdict(data)
                )

        # 完成响应
        yield AgentResponse(
            is_complete=True,
            require_input=False,
            content=None,
        )


class SimpleLangGraphAgent(RunnableAgent):
    """基于 LangGraph 的 Agent 实现。返回 str 类型的数据"""

    def __init__(self):
        model = get_chat_model()
        
        @tool
        async def get_current_time() -> str:
            """获取当前本地时间。"""
            return datetime.now().astimezone().isoformat(timespec="seconds")
        
        langchain_agent = create_agent(
            model=model,
            tools=[get_current_time]
        )

        self._agent = langchain_agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        output = await self._agent.ainvoke(
            inputs,  # type: ignore[arg-type]
            config
        )

        message = output["messages"][-1]

        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=message.text,
        )

    async def stream(self, request: AgentRequest, context: RequestContext) -> AsyncIterator[AgentResponse]:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        async for item in self._agent.astream(
            inputs, # type: ignore[arg-type]
            config, stream_mode="values"
        ):
            # 获取最后的消息
            latest_message = item["messages"][-1]

            if isinstance(latest_message, AIMessage):
                if latest_message.text:

                    print(f"Agent: {latest_message.text}")

                    yield  AgentResponse(
                        is_complete=False,
                        require_input=False,
                        content=latest_message.text
                    )
                if latest_message.tool_calls:
                    tool_names = [tc["name"] for tc in latest_message.tool_calls]
                    tool_call = "、".join(tool_names)
                    
                    print(f"Calling tools: {tool_call}")

                    yield  AgentResponse(
                        is_complete=False,
                        require_input=False,
                        content=f"Calling tools {tool_call}"
                    )
            elif isinstance(latest_message, ToolMessage):
                tool_name = latest_message.name
                tool_response = latest_message.text

                print(f"Tool {tool_name} response {tool_response}")

                yield  AgentResponse(
                    is_complete=False,
                    require_input=False,
                    content=f"Tool {tool_name} response {tool_response}"
                )
                
        # 完成响应
        yield AgentResponse(
            is_complete=True,
            require_input=False,
            content=None,
        )


class MultimodalAgent(RunnableAgent):
    """基于 LangGraph 的 Agent 实现。支持多模态输入"""

    def __init__(self):
        model = get_chat_model()
        langchain_agent = create_agent(model=model)

        self._agent = langchain_agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        context_id = request.context_id

        content = None
        if isinstance(request.content, str):
            content = request.content

        if isinstance(request.content, dict):
            # 获取多模态内容。blocks 字段和客户端约定好即可
            content = request.content.get("blocks", [])

        if not content:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=content)]}

        output = await self._agent.ainvoke(
            inputs, # type: ignore[arg-type]
            config
        )

        message = output["messages"][-1]

        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=message.text,
        )

    async def stream(self, request: AgentRequest, context: RequestContext) -> AsyncIterator[AgentResponse]:
        context_id = request.context_id

        content = None
        if isinstance(request.content, str):
            content = request.content

        if isinstance(request.content, dict):
            # 获取多模态内容。
            content = request.content.get("blocks", [])

        if not content:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=content)]}

        async for chunk in self._agent.astream(
            inputs, # type: ignore[arg-type]
            config,
            version="v2",
            stream_mode=["messages", "updates"]
        ):
            if chunk["type"] == "messages":
                token, _metadata = chunk["data"]
                if isinstance(token, AIMessageChunk):
                    yield AgentResponse(
                        is_complete=False,
                        require_input=False,
                        content=token.text
                    )
            elif chunk["type"] == "updates":
                for source, update in chunk["data"].items():
                    if source in ("model", "tools"):
                        # 获取最后的消息
                        latest_message = update["messages"][-1]

                        if isinstance(latest_message, AIMessage):
                            if latest_message.text:

                                print(f"Agent: {latest_message.text}")

                                # 完整 AI 消息内容
                                # yield AgentResponse(
                                #     is_complete=False,
                                #     require_input=False,
                                #     content=latest_message.text
                                # )
                            if latest_message.tool_calls:
                                tool_names = [tc["name"] for tc in latest_message.tool_calls]
                                tool_call = "、".join(tool_names)
                                
                                print(f"Calling tools: {tool_call}")

                                yield AgentResponse(
                                    is_complete=False,
                                    require_input=False,
                                    content=f"Calling tools {tool_call}"
                                )
                        elif isinstance(latest_message, ToolMessage):
                            tool_name = latest_message.name
                            tool_response = latest_message.text

                            print(f"Tool {tool_name} response {tool_response}")

                            yield AgentResponse(
                                is_complete=False,
                                require_input=False,
                                content=f"Tool {tool_name} response {tool_response}"
                            )
                
        # 完成响应
        yield AgentResponse(
            is_complete=True,
            require_input=False,
            content=None,
        )
