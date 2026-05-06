import asyncio
import httpx
import uuid
from a2a.client.card_resolver import A2ACardResolver

from a2a_client import A2AClientAgent, AgentRequest

async def main():
    agent_url = "http://127.0.0.1:8080"
    agent_card = None

    async with httpx.AsyncClient(timeout=30) as client:
        resolver = A2ACardResolver(client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()

        # 默认使用 jsonrpc
        client_agent = A2AClientAgent(agent_card=agent_card, httpx_client=client)

        interrupt_id = None
        interrupt = None
        current_context_id = str(uuid.uuid4())
        while True:
            try:
                loop = asyncio.get_running_loop()
                user_input = await loop.run_in_executor(None, input, "You: ")
            except KeyboardInterrupt:
                break

            if user_input.lower() in ("/quit", "/exit"):
                break
            if not user_input.strip():
                continue

            
            request = AgentRequest(content=user_input, context_id=current_context_id)

            if user_input.lower() in ("approve", "reject"):
                if interrupt_id and interrupt:
                    request.resume_id = interrupt_id
                    request.resume = {
                        interrupt["id"]: {
                            "decisions": [{"type": user_input.lower()}]
                        }
                    }

            async for item in client_agent.send_message_streaming(request):
                print(item)
                
                if item.require_input:
                    if item.interrupt_id and item.interrupt:
                        interrupt_id = item.interrupt_id
                        interrupt = item.interrupt
                        print("Interrupt: approve or reject ?")
                        break
                else:
                    interrupt_id = None
                    interrupt = None
                if item.content:
                    print(f"Agent: {item.content}")
                if item.artifact:
                    print(f"Artifact: {item.artifact}")


        await client_agent.close()


if __name__ == "__main__":
    asyncio.run(main())
