import uvicorn
from langchain.agents import create_agent
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentInterface,
)
from a2a_common import PROTOCOL_JSON_RPC, PROTOCOL_HTTP_JSON, PROTOCOL_VERSION_1_0, PROTOCOL_VERSION_0_3
from a2a_server import A2AServerAgent
from examples.langgraph_agent.agent import SimpleLangGraphAgent
from examples.langgraph_agent.chat_model import get_chat_model


def run():
    host = "127.0.0.1"
    port = 8080
    model = get_chat_model()

    langchain_agent = create_agent(model=model)

    runnable_agent = SimpleLangGraphAgent(langchain_agent)

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
        # 协议说明
        supported_interfaces=[
            AgentInterface(
                # A2AServerAgent 处理请求的 url path
                url=f"http://{host}:{port}/a2a/jsonrpc",
                # JSONRPC, HTTP+JSON 或 GRPC
                protocol_binding=PROTOCOL_JSON_RPC, 
                protocol_version=PROTOCOL_VERSION_1_0 # 协议版本 1.0 或 0.3
            ),
            AgentInterface(
                url=f"http://{host}:{port}/a2a/jsonrpc",
                protocol_binding=PROTOCOL_JSON_RPC,
                # 第一个 0.3 版本作为兼容的主协议
                protocol_version=PROTOCOL_VERSION_0_3 # 说明兼容 0.3
            ),
            AgentInterface(
                url=f"http://{host}:{port}/a2a/rest",
                protocol_binding=PROTOCOL_HTTP_JSON,
                protocol_version=PROTOCOL_VERSION_1_0
            ),
            AgentInterface(
                url=f"http://{host}:{port}/a2a/rest",
                protocol_binding=PROTOCOL_HTTP_JSON,
                protocol_version=PROTOCOL_VERSION_0_3 # 说明兼容 0.3
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
        enable_http_v0_3_compat=True # 开启 0.3 版本兼容
    )

    app = server_agent.init_server_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    run()
