import uuid
import httpx
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable
from a2a.client import (
    ClientFactory,
    ClientConfig,
    Client,
    ClientCallInterceptor
)
from a2a_client.converter import (
    RequestPartConverter,
    ResponsePartConverter,
    DefaultRequestPartConverter,
    DefaultResponsePartConverter
)
from a2a.client.optionals import Channel #type: ignore
from a2a.types import (
    AgentCard,
    Message,
    Role,
    TaskState,
    SendMessageRequest,
    StreamResponse,
    GetExtendedAgentCardRequest
)
from a2a.helpers.proto_helpers import  get_message_text
import logging

from a2a_common import PROTOCOL_JSON_RPC
from a2a_client.context import RequestContext, build_call_context, build_metadata


logger = logging.getLogger(__name__)


@dataclass
class AgentRequest:
    """Agent 请求信息"""

    context_id: str
    """对话上下文。通过 context_id 保持对话连贯性"""

    content: str | dict[str, Any] | None
    """消息内容。有中断恢复信息时，该内容无效"""

    resume_id: str | None = None
    """中断恢复 id"""

    resume: dict[str, Any] | None = None
    """中断恢复信息"""


@dataclass
class AgentResponse:
    """Agent 响应信息"""

    content: str | dict[str, Any] | None
    """响应内容"""

    require_input: bool = False
    """是否要求输入，适用于中断的情况"""

    interrupt_id: str | None = None
    """中断 id"""

    interrupt: dict[str, Any] | None = None
    """中断信息"""

    artifact: str | dict[str, Any] | None = None
    """人工制作信息"""


class A2AClientAgent:
    def __init__(
        self,
        agent_card: AgentCard,
        httpx_client: httpx.AsyncClient | None = None,
        protocol_binding: str = PROTOCOL_JSON_RPC,
        request_converter: RequestPartConverter | None = None,
        response_converter: ResponsePartConverter | None = None,
        interceptors: list[ClientCallInterceptor] | None = None,
        grpc_channel_factory: Callable[[str], Channel] | None = None
    ):
        self._agent_card = agent_card
        self._httpx_client = httpx_client
        self._request_converter = request_converter or DefaultRequestPartConverter()
        self._response_converter = response_converter or DefaultResponsePartConverter()

        (client, streaming_client) = self._ensure_client(
                protocol_binding,
                interceptors,
                grpc_channel_factory
            )
        self._client = client
        self._streaming_client = streaming_client

    def _ensure_client(
            self,
            protocol_binding: str,
            interceptors: list[ClientCallInterceptor] | None,
            grpc_channel_factory: Callable[[str], Channel] | None
        ) -> tuple[Client, Client]:

        config = ClientConfig(
            streaming=False,
            httpx_client=self._httpx_client,
            supported_protocol_bindings=[protocol_binding],
            grpc_channel_factory=grpc_channel_factory
        )
        clinet_factory = ClientFactory(config)
        client = clinet_factory.create(self._agent_card, interceptors)

        streaming_config = ClientConfig(
            streaming=True,
            httpx_client=self._httpx_client,
            supported_protocol_bindings=[protocol_binding],
            grpc_channel_factory=grpc_channel_factory
        )
        clinet_factory = ClientFactory(streaming_config)
        streaming_client = clinet_factory.create(self._agent_card, interceptors)

        return (client, streaming_client)

    def get_agent_card(self) -> AgentCard:
        return self._agent_card
    
    async def get_extended_agent_card(self) -> AgentCard:
        if not self._agent_card.capabilities.extended_agent_card:
            return self._agent_card
        
        extended_agent_card = await self._streaming_client.get_extended_agent_card(
            GetExtendedAgentCardRequest()
        )

        if extended_agent_card:
            # The client is instance of BaseClient.
            # Force update client's agent card.
            # The stream client' agent card has updated in get_extended_agent_card. 
            setattr(self._client, "_card", extended_agent_card)
            self._agent_card = extended_agent_card
        
        return self._agent_card

    async def send_message(
        self,
        request: AgentRequest,
        context: RequestContext | None = None
    ) -> AgentResponse:
        """普通响应消息"""

        call_context = None
        metadata = None
        if context:
            call_context = build_call_context(context)
            metadata = build_metadata(context)

        msg = self._create_message(request)
        send_request = SendMessageRequest(message=msg, metadata=metadata)

        response = self._client.send_message(send_request, context=call_context)

        event = await anext(response)

        return self._hand_response(event)

    async def send_message_streaming(
        self,
        request: AgentRequest,
        context: RequestContext | None = None
    ) -> AsyncIterator[AgentResponse]:
        """流式响应消息"""

        call_context = None
        metadata = None
        if context:
            call_context = build_call_context(context)
            metadata = build_metadata(context)

        msg = self._create_message(request)
        send_request = SendMessageRequest(message=msg, metadata=metadata)

        response = self._streaming_client.send_message(send_request, context=call_context)

        async for event in response:
            agent_response = self._handle_stream_response(event)
            if agent_response is None:
                continue
            yield agent_response

    def _hand_response(self, event: StreamResponse) -> AgentResponse:
        if event.HasField("task"):
            task = event.task
            status = task.status
            latest_message = None
            artifact = None
            if status and status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
                if status.message:
                    interrupt = self._response_converter.convert_interrupt_part(
                        list(status.message.parts)
                    )
                    return AgentResponse(
                        content=None,
                        require_input=True,
                        interrupt_id=status.message.task_id,
                        interrupt=interrupt,
                    )
            if task.history:
                history = [
                    history
                    for history in task.history
                    if history.role == Role.ROLE_AGENT
                ]
                if len(history) > 0:
                    latest_message = history[-1]
            if task.artifacts:
                artifact = task.artifacts[-1]
            return AgentResponse(
                content=self._response_converter.convert_message_part(
                    list(latest_message.parts)
                )
                if latest_message
                else None,
                artifact=self._response_converter.convert_artifact_part(
                    list(artifact.parts)
                )
                if artifact
                else None,
            )
        elif event.HasField("message"):
            return AgentResponse(
                content=self._response_converter.convert_message_part(
                    list(event.message.parts)
                )
            )
        return AgentResponse(content=None)
    
    def _handle_stream_response(self, event: StreamResponse) -> AgentResponse | None:
        if event.HasField("status_update"):
            update = event.status_update
            state = update.status.state
            if state == TaskState.TASK_STATE_WORKING:
                content = None
                if update.status.message:
                    content = self._response_converter.convert_message_part(
                        list(update.status.message.parts)
                    )
                return AgentResponse(content=content)
            elif state == TaskState.TASK_STATE_INPUT_REQUIRED:
                interrupt = None
                if update.status.message:
                    interrupt = self._response_converter.convert_interrupt_part(
                        list(update.status.message.parts)
                    )
                return AgentResponse(
                    content=None,
                    require_input=True,
                    interrupt_id=update.task_id,
                    interrupt=interrupt,
                )
            elif state == TaskState.TASK_STATE_FAILED:
                msg = ""
                if update.status.message:
                    msg = get_message_text(update.status.message)
            
                raise ValueError(f"Agent {self._agent_card.name} task {update.task_id} is faied: {msg}")
        elif event.HasField("artifact_update"):
            artifact = event.artifact_update.artifact
            return AgentResponse(
                content=None,
                artifact=self._response_converter.convert_artifact_part(
                    list(artifact.parts)
                )
            )
        elif event.HasField("message"):
            return AgentResponse(
                content=self._response_converter.convert_message_part(
                    list(event.message.parts)
                )
            )

        return None

    def _create_message(self, request: AgentRequest) -> Message:
        context_id = request.context_id
        msg = Message(
            context_id=context_id,
            task_id=request.resume_id or "",
            message_id=str(uuid.uuid4()),
            role=Role.ROLE_USER
        )

        if request.resume:
            parts = self._request_converter.convert_resume(request.resume)
            msg.parts.extend(parts)
        elif request.content:
            parts = self._request_converter.convert_content(request.content)
            msg.parts.extend(parts)
        else:
            raise ValueError("AgentRequest must has content or resume")
        
        return msg

    async def close(self):
        await self._client.close()
        await self._streaming_client.close()
