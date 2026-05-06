import uvicorn
from langchain.agents import create_agent
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentInterface,
)
from a2a_common import PROTOCOL_JSON_RPC, PROTOCOL_VERSION_1_0
from a2a_server import A2AServerAgent
from examples.langgraph_agent.agent import SimpleLangGraphAgent
from examples.langgraph_agent.chat_model import get_chat_model


def run():
    host = "127.0.0.1"
    port = 8080
    model = get_chat_model()
    langchain_agent = create_agent(model=model)

    simple_runnable_agent = SimpleLangGraphAgent(langchain_agent)

    public_skill = AgentSkill(
        id="public_test",
        name="公开的技能",
        description="公开的技能测试",
        tags=["你好"],
        examples=["你好", "hello"],
        input_modes=["text/plain", "application/json"],
        output_modes=["text/plain", "application/json"],
    )

    extended_skill = AgentSkill(
        id="extend_test",
        name="扩展的技能测试",
        description="扩展的技能测试",
        tags=["你好", "扩展"],
        examples=["你好", "hello", "给我一个扩展"],
        input_modes=["text/plain", "application/json"],
        output_modes=["text/plain", "application/json"],
    )

    public_agent_card = AgentCard(
        name="a2a_server_agent",
        description="测试公开的A2A服务",
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
        capabilities=AgentCapabilities(
            streaming=True,
            extended_agent_card=True # 支持扩展的 agent card
        ),
        skills=[public_skill], # 公开的技能
    )

    extended_agent_card = AgentCard(
        name="a2a_server_extended_agent",
        description="测试扩展的A2A服务",
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
        capabilities=AgentCapabilities(
            streaming=True,
            extended_agent_card=True
        ),
        skills=[public_skill, extended_skill], # 公开和扩展的技能
    )

    server_agent = A2AServerAgent(
        agent=simple_runnable_agent,
        agent_card=public_agent_card,
        extended_agent_card=extended_agent_card,
    )

    app = server_agent.init_server_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    run()
