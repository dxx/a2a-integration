import sys_path

import uvicorn
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentInterface,
)

from a2a_common import PROTOCOL_JSON_RPC, PROTOCOL_VERSION_1_0
from a2a_server import A2AServerAgent
from examples.langgraph_agent.agent import SimpleLangGraphAgent
from examples.converter.server_converter import CustomRequestPartConverter, CustomResponsePartConverter


def run():
    host = "127.0.0.1"
    port = 8080

    runnable_agent = SimpleLangGraphAgent()

    skill = AgentSkill(
        id="test",
        name="技能测试",
        description="测试",
        tags=["你好"],
        examples=["你好", "hello"],
        input_modes=["text/plain", "application/json"],
        output_modes=["text/plain", "application/json"],
    )

    agent_card = AgentCard(
        name="a2a_server_agent",
        description="测试A2A服务",
        supported_interfaces=[
            AgentInterface(
                url=f"http://{host}:{port}/a2a/jsonrpc",
                protocol_binding=PROTOCOL_JSON_RPC, 
                protocol_version=PROTOCOL_VERSION_1_0
            )
        ],
        version="0.0.1",
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    server_agent = A2AServerAgent(
        agent=runnable_agent,
        agent_card=agent_card,
        # 使用自定义 part 转换器
        request_converter=CustomRequestPartConverter(),
        response_converter=CustomResponsePartConverter()
    )

    app = server_agent.init_server_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    run()
