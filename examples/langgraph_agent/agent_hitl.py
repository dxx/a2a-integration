import re
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from typing import AsyncIterator
from dataclasses import asdict 
from pathlib import Path

from a2a_server import RunnableAgent, AgentRequest, AgentResponse, RequestContext
from examples.langgraph_agent.chat_model import get_chat_model

@tool(parse_docstring=True)
def read_file(file_path: str) -> str:
    """读取文件内容
    
    Args:
        file_path: 文件路径
    """

    file_path = resolve_path(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        return content

@tool(parse_docstring=True)
def write_file(file_path: str, content: str) -> str:
    """写入文件
    
    Args:
        file_path: 文件路径
        content: 写入文件的内容
    """

    file_path = resolve_path(file_path)

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return "写入文件成功"


def resolve_path(file_path: str) -> str:
    path = ""
    if file_path.startswith("/"):
        path = file_path
    elif re.search(r"^[a-zA-Z]+:", file_path):
        path = file_path
    else:
        script_dir = Path(__file__).resolve().parent
        path = str(script_dir) + "/" + file_path.removeprefix("./")
    return path



class HITLLangGraphAgent(RunnableAgent):
    """基于 LangGraph 支持 Human-in-the-loop 的 Agent 实现。返回 str 类型的数据"""

    def __init__(self):
        self._agent = create_agent(
            model=get_chat_model(),
            tools=[read_file, write_file],
            checkpointer=InMemorySaver(),
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on={
                        "read_file": False, # 不需要审批
                        "write_file": {
                            # 可选的审批
                            "allowed_decisions": ["approve", "reject"],
                            # 审批描述
                            #"description": "写入文件需要审批"
                            # 可以是可调用函数
                            "description": lambda tool_call, state, runtime: f"调用了 {tool_call["name"]} 工具，写入文件需要审批"
                        }
                    },
                    # 未指定审批描述时的内容
                    # description_prefix="审批提醒："
                )
            ]
        )

    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:

        print(f"context={context}")

        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query and not request.resume:
            raise ValueError("Content is invalid")
        
        inputs = {"messages": [HumanMessage(content=query)]}

        if request.resume:
            inputs = Command(resume=request.resume)
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}

        output = await self._agent.ainvoke(
            inputs, # type: ignore[arg-type]
            config,
            version="v2"
        )

        # 中断信息
        interrupts = output.interrupts

        if interrupts:
            interrupt = interrupts[0]
            return AgentResponse(
                require_input=True,
                content=None,
                interrupt=asdict(interrupt)
            )

        message = output.value["messages"][-1]

        return AgentResponse(
            is_complete=True,
            require_input=False,
            content=message.text,
        )

    async def stream(self, request: AgentRequest, context: RequestContext) -> AsyncIterator[AgentResponse]:
                
        print(f"context={context}")

        context_id = request.context_id

        query = ""
        if isinstance(request.content, str):
            query = request.content
        if not query and not request.resume:
            raise ValueError("Content is invalid")
        
        inputs = {"messages": [HumanMessage(content=query)]}
        
        if request.resume:
            inputs = Command(resume=request.resume)
        
        config: RunnableConfig = {"configurable": {"thread_id": context_id}}

        async for chunk in self._agent.astream(
            inputs, # type: ignore[arg-type]
            config,
            version="v2",
            stream_mode=["updates"]
        ):
            if chunk["type"] != "updates":
                continue
            
            for source, update in chunk["data"].items():
                if source == "__interrupt__":
                    interrupt = update[0]
                    yield AgentResponse(
                        require_input=True,
                        content=None,
                        interrupt=asdict(interrupt)
                    )
                    break
                if source in ("model", "tools"):
                    # 获取最后的消息
                    latest_message = update["messages"][-1]

                    if isinstance(latest_message, AIMessage):
                        if latest_message.text:

                            print(f"Agent: {latest_message.text}")

                            yield AgentResponse(
                                is_complete=False,
                                require_input=False,
                                content=latest_message.text
                            )
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
