import httpx
from a2a.client.card_resolver import A2ACardResolver

from a2a_client import A2AClientAgent, AgentRequest

async def main():
    agent_url = "http://127.0.0.1:8080"

    async with httpx.AsyncClient(timeout=30) as client:
        resolver = A2ACardResolver(client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()

        client_agent = A2AClientAgent(agent_card=agent_card, httpx_client=client)

        content = {
            "blocks": [ # blocks 字段和服务端约定好即可
                # OpenAI 兼容格式
                {"type": "image_url", "image_url": {"url": "https://img0.baidu.com/it/u=2944321954,3468161118&fm=253&app=138&f=JPEG?w=800&h=1400"}},
                {"type": "text", "text": "描述下这个图片"}
            ]
        }
        
        request = AgentRequest(content=content, context_id="user_id")

        async for item in client_agent.send_streaming_message(request):
            print(f"流式响应消息: {item}")


        await client_agent.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
