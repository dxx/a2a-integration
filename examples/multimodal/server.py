import sys_path

import uvicorn
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentInterface,
)
from a2a_common import PROTOCOL_JSON_RPC, PROTOCOL_VERSION_1_0, PROTOCOL_VERSION_0_3
from a2a_server import A2AServerAgent
from examples.langgraph_agent.agent import MultimodalAgent


def run():
    host = "127.0.0.1"
    port = 8080
    
    runnable_agent = MultimodalAgent()

    skill = AgentSkill(
        id="test",
        name="多模态",
        description="测试多模态",
        tags=["这是什么内容"],
        examples=["这是什么内容", "hello"],
        input_modes=["text/plain", "application/json"],
        output_modes=["text/plain", "application/json"],
    )

    agent_card = AgentCard(
        name="a2a_server_agent",
        description="测试A2A服务",
        # 协议说明
        supported_interfaces=[
            AgentInterface(
                # A2AServerAgent 处理请求的 url path
                url=f"http://{host}:{port}/a2a/multimodal",
                # JSONRPC, HTTP+JSON 或 GRPC
                protocol_binding=PROTOCOL_JSON_RPC, 
                protocol_version=PROTOCOL_VERSION_1_0 # 协议版本 1.0 或 0.3
            ),
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
    )

    app = server_agent.init_server_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    run()
