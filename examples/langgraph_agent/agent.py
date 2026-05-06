
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from typing import AsyncIterator, Literal
from dataclasses import dataclass, asdict 

from a2a_server import RunnableAgent, AgentRequest, AgentResponse, RequestContext

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

    def __init__(self, agent: Runnable):
        self._agent = agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        output = await self._agent.ainvoke(inputs, config)

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
            artifact="Finished"
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
            inputs, config, stream_mode="values"
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
            artifact="Finished"
        )


class SimpleLangGraphAgent(RunnableAgent):
    """基于 LangGraph 的 Agent 实现。返回 str 类型的数据"""

    def __init__(self, agent: Runnable):
        self._agent = agent

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query:
            raise ValueError("Content is invalid")
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}
        inputs = {"messages": [HumanMessage(content=query)]}

        output = await self._agent.ainvoke(inputs, config)

        message = output["messages"][-1]

        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=message.text,
            artifact="Finished"
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
            inputs, config, stream_mode="values"
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
            artifact="Finished"
        )
