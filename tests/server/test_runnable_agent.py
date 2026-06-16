from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from google.protobuf import json_format
from pytest_mock import MockerFixture

from a2a.types import (
    InvalidParamsError,
    Task,
    TaskState,
    UnsupportedOperationError,
    Message,
    Part,
)
from a2a.server.agent_execution.context import RequestContext as A2ARequestContext
from a2a.server.events.event_queue_v2 import EventQueueSource
from a2a.server.tasks import TaskUpdater

from a2a_server.agent import (
    RunnableAgent,
    RunnableAgentExecutor,
    AgentRequest,
    AgentResponse,
    RequestContext,
)


class EchoAgent(RunnableAgent):
    """默认的 RunnableAgent 实现，用于测试。"""

    def __init__(self, responses: list[AgentResponse] | None = None) -> None:
        self.responses = responses or []
        self.invoke_calls: list[tuple[AgentRequest, RequestContext]] = []
        self.stream_calls: list[tuple[AgentRequest, RequestContext]] = []

    async def invoke(
        self, request: AgentRequest, context: RequestContext
    ) -> AgentResponse:
        self.invoke_calls.append((request, context))
        if self.responses:
            return self.responses.pop(0)
        return AgentResponse(content="echo", is_complete=True)

    async def stream(self, request: AgentRequest, context: RequestContext):
        self.stream_calls.append((request, context))
        for resp in self.responses:
            yield resp


def _make_task(task_id: str = "task-1", context_id: str = "ctx-1") -> Task:
    task = Task()
    task.id = task_id
    task.context_id = context_id
    return task


def _make_message(content: str) -> Message:
    msg = Message()
    msg.context_id = "ctx-1"
    msg.task_id = "task-1"
    part = msg.parts.add()
    json_format.ParseDict({"content": content}, part.data)
    return msg


def _make_a2a_context(
    mocker: MockerFixture,
    task: Task | None = None,
    message: Message | None = None,
    method: str = "/jsonrpc",
) -> MagicMock:
    mock_call_context = mocker.MagicMock()
    mock_call_context.state = {"method": method}

    ctx = mocker.MagicMock(spec=A2ARequestContext)
    ctx.call_context = mock_call_context
    ctx.current_task = task
    ctx.message = message
    ctx.task_id = task.id if task else None
    ctx.context_id = task.context_id if task else None
    return ctx


class TestRunnableAgentExecutor:

    @pytest_asyncio.fixture
    async def event_queue(self) -> EventQueueSource:
        return EventQueueSource()

    @pytest.fixture
    def mock_updater(self, mocker: MockerFixture) -> MagicMock:
        updater = mocker.MagicMock(spec=TaskUpdater)
        updater.start_work = mocker.AsyncMock()
        updater.update_status = mocker.AsyncMock()
        updater.add_artifact = mocker.AsyncMock()
        updater.complete = mocker.AsyncMock()
        updater.requires_input = mocker.AsyncMock()
        return updater

    @pytest.fixture
    def mock_build_request_context(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch(
            "a2a_server.agent.build_request_context",
            return_value=RequestContext(header_parameters={}, request_metadata={}),
        )

    @pytest.fixture
    def mock_task_updater_cls(
        self, mocker: MockerFixture, mock_updater: MagicMock
    ) -> MagicMock:
        return mocker.patch(
            "a2a_server.agent.TaskUpdater",
            return_value=mock_updater,
        )

    # execute - invoke complete
    @pytest.mark.asyncio
    async def test_execute_invoke_complete(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(responses=[AgentResponse(content="done", is_complete=True)])
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=_make_message("hello"))

        await executor.execute(a2a_ctx, event_queue)

        assert len(agent.invoke_calls) == 1
        req, ctx = agent.invoke_calls[0]
        assert req.context_id == "ctx-1"
        assert req.content == "hello"

        mock_updater.start_work.assert_called_once()
        mock_updater.add_artifact.assert_called_once()
        mock_updater.complete.assert_called_once()

    # execute - invoke with artifact
    @pytest.mark.asyncio
    async def test_execute_invoke_with_artifact(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(
            responses=[
                AgentResponse(content="done", is_complete=True)
            ]
        )
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=_make_message("hello"))

        await executor.execute(a2a_ctx, event_queue)

        mock_updater.add_artifact.assert_called_once()
        mock_updater.complete.assert_called_once()

    # execute - invoke require_input with interrupt
    @pytest.mark.asyncio
    async def test_execute_invoke_require_input(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(
            responses=[
                AgentResponse(
                    content=None,
                    is_complete=False,
                    require_input=True,
                    interrupt={"action": "pause"},
                )
            ]
        )
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=_make_message("hello"))

        await executor.execute(a2a_ctx, event_queue)

        mock_updater.requires_input.assert_called_once()
        mock_updater.complete.assert_not_called()

    # execute - invoke require_input without interrupt
    @pytest.mark.asyncio
    async def test_execute_invoke_require_input_no_interrupt(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(
            responses=[
                AgentResponse(
                    content=None,
                    is_complete=False,
                    require_input=True,
                    interrupt=None,
                )
            ]
        )
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=_make_message("hello"))

        await executor.execute(a2a_ctx, event_queue)

        mock_updater.requires_input.assert_not_called()
        mock_updater.update_status.assert_called_once()
        call_args = mock_updater.update_status.call_args
        assert call_args.kwargs["state"] == TaskState.TASK_STATE_FAILED
        assert "interrupt is required" in str(call_args.kwargs["message"])

    # execute - stream complete
    @pytest.mark.asyncio
    async def test_execute_stream_complete(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(
            responses=[
                AgentResponse(content="chunk1", is_complete=False),
                AgentResponse(content="chunk2", is_complete=False),
                AgentResponse(content="final", is_complete=True),
            ]
        )
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(
            mocker, task=task, message=_make_message("hello"), method="/message:stream"
        )

        await executor.execute(a2a_ctx, event_queue)

        assert len(agent.stream_calls) == 1
        mock_updater.start_work.assert_called_once()
        assert mock_updater.add_artifact.call_count == 3
        mock_updater.complete.assert_called_once()

    # execute - stream require_input
    @pytest.mark.asyncio
    async def test_execute_stream_require_input(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(
            responses=[
                AgentResponse(content="chunk1", is_complete=False),
                AgentResponse(
                    content=None,
                    is_complete=False,
                    require_input=True,
                    interrupt={"action": "pause"},
                ),
            ]
        )
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(
            mocker, task=task, message=_make_message("hello"), method="/message:stream"
        )

        await executor.execute(a2a_ctx, event_queue)

        mock_updater.requires_input.assert_called_once()
        mock_updater.complete.assert_not_called()

    # execute - message is none raises InvalidParamsError
    @pytest.mark.asyncio
    async def test_execute_message_none_raises(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_build_request_context: MagicMock,
    ) -> None:
        agent = EchoAgent()
        executor = RunnableAgentExecutor(agent=agent)

        a2a_ctx = _make_a2a_context(mocker, task=None, message=None)

        with pytest.raises(InvalidParamsError, match="Message is empty"):
            await executor.execute(a2a_ctx, event_queue)

    # execute - exception handling
    @pytest.mark.asyncio
    async def test_execute_exception_handling(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        class FailingAgent(RunnableAgent):
            async def invoke(
                self, request: AgentRequest, context: RequestContext
            ) -> AgentResponse:
                raise RuntimeError("boom")

            async def stream(self, request: AgentRequest, context: RequestContext):
                yield await self.invoke(request, context)

        agent = FailingAgent()
        executor = RunnableAgentExecutor(agent=agent)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=_make_message("hello"))

        await executor.execute(a2a_ctx, event_queue)

        mock_updater.update_status.assert_called_once()
        call_args = mock_updater.update_status.call_args
        assert call_args.kwargs["state"] == TaskState.TASK_STATE_FAILED

    # execute - resume clears content
    @pytest.mark.asyncio
    async def test_execute_resume_clears_content(
        self,
        mocker: MockerFixture,
        event_queue: EventQueueSource,
        mock_updater: MagicMock,
        mock_build_request_context: MagicMock,
        mock_task_updater_cls: MagicMock,
    ) -> None:
        agent = EchoAgent(responses=[AgentResponse(content="done", is_complete=True)])
        executor = RunnableAgentExecutor(agent=agent)

        msg = Message()
        msg.context_id = "ctx-1"
        msg.task_id = "task-1"
        part = msg.parts.add()
        data = {
            "resume": {"decisions": [{"type": "approve"}]},
            "content": "should_be_ignored",
        }
        json_format.ParseDict(data, part.data)

        task = _make_task()
        a2a_ctx = _make_a2a_context(mocker, task=task, message=msg)

        await executor.execute(a2a_ctx, event_queue)

        req, _ = agent.invoke_calls[0]
        assert req.resume == {"decisions": [{"type": "approve"}]}
        assert req.content is None

    # cancel raises UnsupportedOperationError
    @pytest.mark.asyncio
    async def test_cancel_raises(
        self, mocker: MockerFixture, event_queue: EventQueueSource
    ) -> None:
        agent = EchoAgent()
        executor = RunnableAgentExecutor(agent=agent)

        a2a_ctx = _make_a2a_context(mocker)

        with pytest.raises(UnsupportedOperationError):
            await executor.cancel(a2a_ctx, event_queue)
