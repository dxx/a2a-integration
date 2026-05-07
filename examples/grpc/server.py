import sys_path

import uvicorn
import grpc
import asyncio
from langchain.agents import create_agent
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentInterface,
)
from a2a_common import PROTOCOL_GRPC, PROTOCOL_VERSION_1_0, PROTOCOL_VERSION_0_3
from a2a_server import A2AServerAgent
from a2a_server.grpc import init_grpc_server, init_compat_grpc_server
from examples.langgraph_agent.agent import LangGraphAgent
from examples.langgraph_agent.chat_model import get_chat_model


async def run():
    host = "127.0.0.1"
    port = 8080
    grpc_port = 18080
    compat_grpc_port = 18081

    model = get_chat_model()
    langchain_agent = create_agent(model=model)

    runnable_agent = LangGraphAgent(langchain_agent)

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
                url=f"{host}:{grpc_port}",
                protocol_binding=PROTOCOL_GRPC,
                protocol_version=PROTOCOL_VERSION_1_0,
            ),
            AgentInterface(
                url=f"{host}:{compat_grpc_port}",
                protocol_binding=PROTOCOL_GRPC,
                # 第一个 0.3 版本作为兼容的主协议
                protocol_version=PROTOCOL_VERSION_0_3,  # 说明兼容 0.3
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
        enable_http_v0_3_compat=True,  # 开启 0.3 版本兼容
    )

    server_app = server_agent.init_server_app()

    handler = server_agent.request_handler()

    grpc_server = grpc.aio.server()
    grpc_server.add_insecure_port(f"{host}:{grpc_port}")

    init_grpc_server(grpc_server, handler)

    # 兼容旧版本的 grpc 服务
    compat_grpc_server = grpc.aio.server()
    compat_grpc_server.add_insecure_port(f"{host}:{compat_grpc_port}")

    init_compat_grpc_server(compat_grpc_server, handler)

    config = uvicorn.Config(server_app, host=host, port=port)
    uvicorn_server = uvicorn.Server(config)

    try:
        await asyncio.gather(
            grpc_server.start(),
            compat_grpc_server.start(),
            uvicorn_server.serve(), # 阻塞等待服务
        )
    except asyncio.exceptions.CancelledError:
        ...
    finally:
        await grpc_server.stop(None)
        await compat_grpc_server.stop(None)


if __name__ == "__main__":
    asyncio.run(run())
