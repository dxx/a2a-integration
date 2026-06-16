from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from dataclasses import dataclass
from starlette.applications import Starlette
from starlette.routing import BaseRoute

from a2a.types import (
    AgentCard,
    Message,
    Task,
    TaskState,
    UnsupportedOperationError,
    InvalidParamsError,
)
from a2a.server.request_handlers import (
    RequestHandler,
    DefaultRequestHandler,
)
from a2a.server.events.event_queue import EventQueue
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext as A2ARequestContext
from a2a.server.tasks import InMemoryTaskStore

from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.server.routes.agent_card_routes import create_agent_card_routes

from a2a.helpers.proto_helpers import (
    new_message,
    new_text_message,
    new_task_from_user_message,
)
from a2a.server.tasks import TaskUpdater
from urllib.parse import urlparse
import json
import logging

from a2a_server.converter import (
    RequestPartConverter,
    ResponsePartConverter,
    DefaultRequestPartConverter,
    DefaultResponsePartConverter,
)
from a2a_server.context import (
    HTTPRestStreamingAwareContextBuilder,
    RequestContext,
    build_request_context
)
from a2a_common.constants import (
    PROTOCOL_JSON_RPC,
    PROTOCOL_HTTP_JSON,
    PROTOCOL_GRPC,
    METHOD_STREAM_JSON_RPC_1_0,
    METHOD_STREAM_JSON_RPC_0_3,
    METHOD_STREAM_HTTP_JSON,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentRequest:
    """Agent 请求信息"""

    context_id: str
    """对话上下文。通过 context_id 保持对话连贯性"""

    content: str | dict[str, Any] | None
    """消息内容。有中断恢复信息时，该内容无效"""

    resume: dict[str, Any] | None = None
    """中断后继续信息"""


@dataclass
class AgentResponse:
    """Agent 响应信息"""

    content: str | dict[str, Any] | None
    """响应内容"""

    is_complete: bool = False
    """是否完成"""

    require_input: bool = False
    """是否要求输入，适用于中断的情况"""

    interrupt: dict[str, Any] | None = None
    """中断信息"""


class RunnableAgent(ABC):
    """Agent 抽象类"""

    @abstractmethod
    async def invoke(self, request: AgentRequest, context: RequestContext) -> AgentResponse:
        """处理方法"""

    @abstractmethod
    async def stream(self, request: AgentRequest, context: RequestContext) -> AsyncIterator[AgentResponse]:
        """流式处理方法"""
        yield await self.invoke(request, context)


class RunnableAgentExecutor(AgentExecutor):
    def __init__(
        self,
        agent: RunnableAgent,
        request_converter: RequestPartConverter | None = None,
        response_converter: ResponsePartConverter | None = None,
    ):
        self._runnable_agent = agent
        self._request_converter = request_converter or DefaultRequestPartConverter()
        self._response_converter = response_converter or DefaultResponsePartConverter()

    async def execute(self, context: A2ARequestContext, event_queue: EventQueue) -> None:

        request_context = build_request_context(context)

        task = context.current_task
        if context.message == None:
            raise InvalidParamsError("Message is empty")
        
        if not task:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        method = METHOD_STREAM_JSON_RPC_1_0
        if context.call_context:
            method = context.call_context.state.get(
                "method", METHOD_STREAM_JSON_RPC_1_0
            )

        request = self._create_request(context.message)

        try:
            if method in (
                METHOD_STREAM_JSON_RPC_1_0,
                METHOD_STREAM_JSON_RPC_0_3,
                METHOD_STREAM_HTTP_JSON,
            ):
                await self._execute_stream(request, task, updater, request_context)
                return
            # 非流式调用
            await self._execute_invoke(request, task, updater, request_context)
        except Exception as e:
            logger.error("Execute error", exc_info=e)
            # 更新失败
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(
                    f"execute fail. {str(e)}", task.context_id, task.id
                ),
            )

    async def cancel(self, context: A2ARequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError()

    async def _execute_invoke(
        self,
        request: AgentRequest,
        task: Task,
        updater: TaskUpdater,
        context: RequestContext
    ) -> None:
        # 处理中
        await updater.start_work(
            new_text_message(
                text="working",
                context_id=task.context_id,
                task_id=task.id,
            )
        )

        # 非流式调用
        response = await self._runnable_agent.invoke(request, context)
        is_complete = response.is_complete
        require_input = response.require_input
        content = response.content
        if require_input:
            if not response.interrupt:
                raise ValueError(f"interrupt is required")
            message = new_message(
                parts=self._response_converter.convert_interrupt(
                    response.interrupt
                ),
                context_id=task.context_id,
                task_id=task.id,
            )
            # 要求输入
            await updater.requires_input(message=message)
            return
        else:
            if content:
                await updater.add_artifact(
                    name="result",
                    parts=self._response_converter.convert_content(content),
                    last_chunk=True,
                )
        if is_complete:
            # 完成
            await updater.complete()

    async def _execute_stream(
        self,
        request: AgentRequest,
        task: Task,
        updater: TaskUpdater,
        context: RequestContext
    ) -> None:
        # 处理中
        await updater.start_work(
            new_text_message(
                text="working",
                context_id=task.context_id,
                task_id=task.id,
            )
        )

        # 流式调用
        async for item in self._runnable_agent.stream(request, context):
            is_task_complete = item.is_complete
            require_user_input = item.require_input
            content = item.content
            if require_user_input:
                if not item.interrupt:
                    raise ValueError(f"interrupt is required")
                message = new_message(
                    parts=self._response_converter.convert_interrupt(
                        item.interrupt
                    ),
                    context_id=task.context_id,
                    task_id=task.id,
                )
                # 要求输入
                await updater.requires_input(message=message)
                break
            elif is_task_complete:
                if content:
                    await updater.add_artifact(
                        name="chunk",
                        parts=self._response_converter.convert_content(content),
                        last_chunk=True,
                    )
                # 完成
                await updater.complete()
            else:
                if content:
                    await updater.add_artifact(
                        name="chunk",
                        parts=self._response_converter.convert_content(content),
                        last_chunk=False,
                    )
    
    def _create_request(self, message: Message) -> AgentRequest:
        request = AgentRequest(context_id=message.context_id, content=None)

        request.resume = self._request_converter.convert_resume_part(
            list(message.parts)
        )
        # 有中断恢复，提取消息内容
        if not request.resume:
            request.content = self._request_converter.convert_message_part(
                list(message.parts)
            )
            request.resume = None

        return request


class A2AServerAgent:
    def __init__(
        self,
        agent: RunnableAgent,
        agent_card: AgentCard,
        extended_agent_card: AgentCard | None = None,
        request_converter: RequestPartConverter | None = None,
        response_converter: ResponsePartConverter | None = None,
        enable_http_v0_3_compat: bool = False,
    ):
        self._agent = agent
        self._agent_card = agent_card
        self._extended_agent_card = extended_agent_card
        self._request_converter = request_converter
        self._response_converter = response_converter
        self._enable_v0_3_compat = enable_http_v0_3_compat

        self._agent_executor = self._create_agent_executor()
        self._request_handler = self._create_request_handler()

    def init_server_app(self) -> Starlette:
        """初始化 HTTP 服务的 App"""

        routers = self._create_http_routers()
        app = Starlette(routes=routers)

        return app

    def request_handler(self) -> RequestHandler:
        if not self._request_handler:
            self._create_request_handler()
        return self._request_handler
    
    def _create_agent_executor(self) -> RunnableAgentExecutor:
        if not self._agent:
            raise ValueError("RunnableAgent is none")

        return RunnableAgentExecutor(
            agent=self._agent,
            request_converter=self._request_converter,
            response_converter=self._response_converter,
        )

    def _create_request_handler(self) -> RequestHandler:
        if not self._agent_card:
            raise ValueError("AgentCard is none")

        task_store = InMemoryTaskStore()
        return DefaultRequestHandler(
            agent_executor=self._agent_executor,
            task_store=task_store,
            agent_card=self._agent_card,
            extended_agent_card=self._extended_agent_card,
        )

    def _create_http_routers(self) -> list[BaseRoute]:
        """创建 HTTP 服务路由"""

        supported_interfaces = self._agent_card.supported_interfaces

        if not supported_interfaces and len(supported_interfaces) <= 0:
            raise InvalidParamsError("AgentCard's supported_interfaces is empty")

        routers = []

        routers.extend(create_agent_card_routes(self._agent_card))

        added_protocol: dict[str, list[str]] = {}

        for interface in supported_interfaces:
            protocol = interface.protocol_binding

            if protocol == PROTOCOL_GRPC:
                # GRPC 协议使用 grpc 模块中的 init_grpc_server 初始化
                continue

            path_prefix = _get_path_prefix(interface.url)

            if protocol in added_protocol and path_prefix in added_protocol[protocol]:
                continue

            if protocol == PROTOCOL_JSON_RPC:
                routers.extend(
                    create_jsonrpc_routes(
                        request_handler=self._request_handler,
                        rpc_url=path_prefix or "/",
                        enable_v0_3_compat=self._enable_v0_3_compat,
                    )
                )
            elif protocol == PROTOCOL_HTTP_JSON:
                routers.extend(
                    create_rest_routes(
                        request_handler=self._request_handler,
                        path_prefix=path_prefix,
                        enable_v0_3_compat=self._enable_v0_3_compat,
                        context_builder=HTTPRestStreamingAwareContextBuilder(),
                    )
                )
            else:
                logger.warning(f"Unsupported protocol binding: {protocol}")

            prefixs = added_protocol.get(protocol, [])
            if len(prefixs) == 0:
                added_protocol[protocol] = prefixs
            prefixs.append(path_prefix)

        return routers


def _get_path_prefix(url: str) -> str:
    """从 HTTP URL 中提取 path。"""
    parsed = urlparse(url)
    return parsed.path
