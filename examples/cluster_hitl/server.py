"""集群 + 人工审批服务端示例。

演示如何把 A2A 服务部署成多副本：多个进程共用同一个数据库，task 状态放在
共享存储里，任意副本都能读取其它副本创建的 task。

本示例使用 `HITLLangGraphAgent`（人工审批）。要跨副本续跑被中断的任务，
需要两处共享存储：

1. **A2A task 状态** —— 由 `create_shared_storage()` 提供的 `DatabaseTaskStore`。
   副本 B 才能读到副本 A 创建的 `input-required` 任务。
2. **LangGraph 图状态** —— 由各副本共享的 checkpoint saver。
   副本 B 才能拿到副本 A 被中断时保存的待恢复状态。
   否则 `Command(resume=...)` 会变成空操作且不报错。

启动::

    # 需要数据库，按需选择驱动：
    #   postgresql: postgresql+asyncpg://user:pass@localhost:5432/a2a
    #   mysql:      mysql+aiomysql://user:pass@localhost:3306/a2a
    #   sqlite:     sqlite+aiosqlite://./a2a.db
    uv run python examples/cluster_hitl/server.py \
        --database-url "postgresql+asyncpg://user:pass@localhost:5432/a2a" \
        --port 8080

多副本启动：把 ``--port`` 换成不同端口，多开几个进程即可。
两个副本必须指向同一个 ``--database-url``；checkpoint 文件固定在
脚本所在目录的 ``checkpoints.sqlite``，跑同一个脚本的副本天然共享。
"""

import argparse
import asyncio
import sys_path
from pathlib import Path

import uvicorn
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)
from a2a_common import PROTOCOL_JSON_RPC, PROTOCOL_VERSION_1_0
from a2a_server import A2AServerAgent
from a2a_server.storage import create_shared_storage
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy.ext.asyncio import create_async_engine

from examples.langgraph_agent.agent_hitl import HITLLangGraphAgent


DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/a2a"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
# LangGraph 图状态的共享存储。各副本必须指向同一个文件。
# 取脚本所在目录的绝对路径 —— 两个副本跑同一个脚本，路径必然一致；
# 若用相对路径，从不同工作目录启动的副本会各写各的文件，
# 表现为「恢复时图再次中断」这种静默失效。
CHECKPOINT_PATH = str(Path(__file__).resolve().parent / "checkpoints.sqlite")
# 停在 input-required / auth-required 的 task 空闲多久后释放运行时占用（秒）。
# 释放后后续请求会从共享存储重建该 task。
INTERRUPTED_TASK_TIMEOUT = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="集群 + 人工审批服务端示例")
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DATABASE_URL,
        help="task 存储与事件流使用的数据库 URL（需带异步驱动）",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="监听地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="监听端口",
    )
    return parser.parse_args()


def make_agent_card(host: str, port: int) -> AgentCard:
    skill = AgentSkill(
        id="cluster_hitl",
        name="集群人工审批示例",
        description="演示多副本部署下 task 的共享与跨副本中断续跑",
        tags=["集群", "多副本", "人工审批"],
        examples=["你好"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )

    return AgentCard(
        name="a2a_cluster_hitl_agent",
        description="集群 + 人工审批 A2A 服务",
        supported_interfaces=[
            AgentInterface(
                url=f"http://{host}:{port}/a2a/jsonrpc",
                protocol_binding=PROTOCOL_JSON_RPC,
                protocol_version=PROTOCOL_VERSION_1_0,
            )
        ],
        version="0.0.1",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


async def main(database_url: str, host: str, port: int) -> None:
    # 共享存储 1：A2A task 状态 + 跨副本事件流。
    # task_store 必须是 VersionedTaskStore 家族，
    # event_stream 必须与它共用同一个 engine，否则跨副本订阅读不到事件。
    engine = create_async_engine(database_url, pool_pre_ping=True)
    storage = create_shared_storage(engine)

    # 共享存储 2：LangGraph 图状态。
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_PATH) as checkpointer:
        server_agent = A2AServerAgent(
            agent=HITLLangGraphAgent(checkpointer=checkpointer),
            agent_card=make_agent_card(host, port),
            shared_storage=storage,
            interrupted_task_timeout=INTERRUPTED_TASK_TIMEOUT,
        )

        # shared_storage 传入后，建表与 engine 的释放都随 Agent 的启停完成。
        app = FastAPI()
        server_agent.attach_app_server(app)

        config = uvicorn.Config(app, host=host, port=port)
        await uvicorn.Server(config).serve()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.database_url, args.host, args.port))
