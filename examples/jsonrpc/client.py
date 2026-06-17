import httpx
from a2a.client.card_resolver import A2ACardResolver

from a2a_client import A2AClientAgent, AgentRequest, RequestContext

async def main():
    agent_url = "http://127.0.0.1:8080"
    agent_card = None

    async with httpx.AsyncClient(timeout=30) as client:
        resolver = A2ACardResolver(client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()

        # 默认使用 jsonrpc
        client_agent = A2AClientAgent(agent_card=agent_card, httpx_client=client)

        request = AgentRequest(content="你好啊", context_id="user_id")

        request_context = RequestContext(
            # metadata 参数
            request_metadata={
                "metadata-key1": "metadata-value1",
                "metadata-key2": ["metadata-key2-value1", "metadata-key2-value2"]
            },
            # header 头
            header_parameters={"header-key1": "header-value1"}
        )
        async for item in client_agent.send_streaming_message(request, request_context):
            print(item)


        await client_agent.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
