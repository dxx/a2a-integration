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
from examples.langgraph_agent.agent_hitl import HITLLangGraphAgent


def run():
    host = "127.0.0.1"
    port = 8080
    
    # 支持人工介入的 Agent
    hitl_runnable_agent = HITLLangGraphAgent()

    skill = AgentSkill(
        id="test",
        name="人工介入测试",
        description="测试人工介入",
        tags=["读文件", "写文件"],
        examples=["将内容: 你好 写入文件 helle.txt"],
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
        agent=hitl_runnable_agent,
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
