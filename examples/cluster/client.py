"""集群模式客户端示例。

演示跨副本的人工审批（Human-in-the-Loop）：

1. 第一轮把请求发给**副本 1**，Agent 触发中断（写入文件需要审批），
   返回 `input-required` 状态；
2. 第二轮带着审批决定发给**副本 2**，由副本 2 读出同一个 task 并续跑完成。

能这样跑通需要两处共享存储（见 `examples/cluster/server.py`）：

- A2A task 状态：副本 2 才能读到副本 1 创建的 `input-required` task；
- LangGraph 图状态：副本 2 才能拿到副本 1 被中断时保存的待恢复状态。

运行（先启动两个副本）::

    uv run python examples/cluster/client.py

环境变量：

- ``A2A_REPLICA1_URL`` 副本 1 地址，默认 ``http://127.0.0.1:8080``
- ``A2A_REPLICA2_URL`` 副本 2 地址，默认 ``http://127.0.0.1:8081``
"""

import asyncio
import os
import sys_path

import httpx
import uuid

from a2a.client.card_resolver import A2ACardResolver
from a2a_client import A2AClientAgent, AgentRequest


REPLICA1_URL = os.environ.get("A2A_REPLICA1_URL", "http://127.0.0.1:8080")
REPLICA2_URL = os.environ.get("A2A_REPLICA2_URL", "http://127.0.0.1:8081")


async def make_client(base_url: str, httpx_client: httpx.AsyncClient) -> A2AClientAgent:
    resolver = A2ACardResolver(httpx_client, base_url=base_url)
    agent_card = await resolver.get_agent_card()
    return A2AClientAgent(agent_card=agent_card, httpx_client=httpx_client)


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as httpx_client:
        client_1 = await make_client(REPLICA1_URL, httpx_client)
        client_2 = await make_client(REPLICA2_URL, httpx_client)

        # context_id 同时是 LangGraph 的 thread_id，
        # 两个副本据此访问同一份对话状态。
        context_id = str(uuid.uuid4())

        print(f"副本1 = {REPLICA1_URL}")
        print(f"副本2 = {REPLICA2_URL}")
        print(f"context_id = {context_id}\n")

        # ---------- 第一轮：发给副本 1，触发中断 ----------
        print(f"[1/2] 副本1 处理：{REPLICA1_URL}")
        request = AgentRequest(
            context_id=context_id,
            content="将内容: 你好 写入文件 hello.txt",
        )

        interrupt_id = None
        interrupt = None
        async for item in client_1.send_streaming_message(request):
            if item.require_input:
                interrupt_id = item.interrupt_id
                interrupt = item.interrupt
                print(f"  -> 触发中断，task_id={interrupt_id}")
                print(f"  -> 中断信息={interrupt}")
                break
            elif item.content:
                print(f"  Agent: {item.content}")

        if not interrupt_id or not interrupt:
            print("没有触发中断，示例结束")
            await client_1.close()
            await client_2.close()
            return

        # ---------- 第二轮：发给副本 2，续跑 ----------
        print(f"\n[2/2] 副本2 恢复：{REPLICA2_URL}")
        request = AgentRequest(
            context_id=context_id,
            content=None,
            # 中断恢复必须带上 task_id，服务端据此定位同一个 task
            resume_id=interrupt_id,
            resume={
                interrupt["id"]: {
                    "decisions": [{"type": "approve"}],
                }
            },
        )

        async for item in client_2.send_streaming_message(request):
            if item.require_input:
                print(f"  -> 仍在等待输入: {item.interrupt}")
                break
            if item.content:
                print(f"  Agent: {item.content}")

        print("\n完成：中断发生在副本 1，恢复由副本 2 完成。")

        await client_1.close()
        await client_2.close()


if __name__ == "__main__":
    asyncio.run(main())
