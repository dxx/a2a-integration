import sys_path

import httpx
from a2a.client.card_resolver import A2ACardResolver

from a2a_client import A2AClientAgent, AgentRequest
from examples.converter.client_converter import CustomRequestPartConverter, CustomResponsePartConverter


async def main():
    agent_url = "http://127.0.0.1:8080"
    agent_card = None

    async with httpx.AsyncClient(timeout=30) as client:
        resolver = A2ACardResolver(client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()

        client_agent = A2AClientAgent(
            agent_card=agent_card,
            httpx_client=client,
            # 使用自定义 part 转换器
            request_converter=CustomRequestPartConverter(),
            response_converter=CustomResponsePartConverter(),
        )

        request = AgentRequest(content="你好啊", context_id="user_id")

        async for item in client_agent.send_message_streaming(request):
            print(item)


        await client_agent.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
