import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture
from starlette.applications import Starlette
from starlette.testclient import TestClient

from a2a.types import AgentCard
from a2a.server.request_handlers import RequestHandler
from a2a.server.cluster.event_stream import TaskEventStream
from a2a.server.cluster.task_store import VersionedTaskStore
from a2a.server.tasks import InMemoryTaskStore
from a2a_server.agent import (
    A2AServerAgent,
    RunnableAgent,
)
from a2a_server.storage import SharedStorage
from a2a_common.constants import PROTOCOL_JSON_RPC, PROTOCOL_HTTP_JSON, PROTOCOL_GRPC
from fastapi import FastAPI


def _make_agent_card(**kwargs) -> AgentCard:
    card = AgentCard()
    card.name = kwargs.get("name", "test-agent")
    card.description = kwargs.get("description", "test")
    for interface in kwargs.get("interfaces", []):
        si = card.supported_interfaces.add()
        si.protocol_binding = interface["protocol_binding"]
        si.url = interface["url"]
    return card


class TestA2AServerAgent:
    @pytest.fixture
    def mock_agent(self, mocker: MockerFixture) -> MagicMock:
        return mocker.MagicMock(spec=RunnableAgent)

    @pytest.fixture
    def agent_card_jsonrpc(self) -> AgentCard:
        return _make_agent_card(
            interfaces=[
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                }
            ]
        )

    @pytest.fixture
    def agent_card_http(self) -> AgentCard:
        return _make_agent_card(
            interfaces=[
                {"protocol_binding": PROTOCOL_HTTP_JSON, "url": "http://localhost/api"}
            ]
        )

    @pytest.fixture
    def agent_card_multi(self) -> AgentCard:
        return _make_agent_card(
            interfaces=[
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                },
                {"protocol_binding": PROTOCOL_HTTP_JSON, "url": "http://localhost/api"},
            ]
        )

    def test_request_handler_returns_handler(
        self, mock_agent: MagicMock, agent_card_jsonrpc: AgentCard
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        handler = agent.request_handler()
        assert handler is not None
        assert isinstance(agent._request_handler, RequestHandler)

    def test_attach_app_server_starlette(
        self, mock_agent: MagicMock, agent_card_jsonrpc: AgentCard
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        app = Starlette()
        agent.attach_app_server(app)
        assert isinstance(app, Starlette)
        assert len(app.routes) > 0

    def test_attach_app_server_fastapi(
        self, mock_agent: MagicMock, agent_card_jsonrpc: AgentCard
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        app = FastAPI()
        agent.attach_app_server(app)
        assert isinstance(app, FastAPI)
        assert len(app.routes) > 0
        # A2A 路由以 Starlette Route 注册
        assert app.openapi()["paths"] == {}

    def test_create_http_routers_jsonrpc(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mocker: MockerFixture,
    ) -> None:
        mock_create_jsonrpc = mocker.patch("a2a_server.agent.create_jsonrpc_routes")
        mock_create_jsonrpc.return_value = []
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])

        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        agent.attach_app_server(Starlette())

        mock_create_jsonrpc.assert_called_once()
        call_kwargs = mock_create_jsonrpc.call_args.kwargs
        assert call_kwargs["rpc_url"] == "/jsonrpc"
        assert call_kwargs["enable_v0_3_compat"] is False

    def test_create_http_routers_http_json(
        self, mock_agent: MagicMock, agent_card_http: AgentCard, mocker: MockerFixture
    ) -> None:
        mock_create_rest = mocker.patch("a2a_server.agent.create_rest_routes")
        mock_create_rest.return_value = []
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])

        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_http)
        agent.attach_app_server(Starlette())

        mock_create_rest.assert_called_once()
        call_kwargs = mock_create_rest.call_args.kwargs
        assert call_kwargs["path_prefix"] == "/api"
        assert call_kwargs["enable_v0_3_compat"] is False

    def test_create_http_routers_skips_grpc(
        self, mock_agent: MagicMock, mocker: MockerFixture
    ) -> None:
        card = _make_agent_card(
            interfaces=[
                {"protocol_binding": PROTOCOL_GRPC, "url": "http://localhost/grpc"}
            ]
        )
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mock_create_jsonrpc = mocker.patch(
            "a2a_server.agent.create_jsonrpc_routes", return_value=[]
        )
        mock_create_rest = mocker.patch(
            "a2a_server.agent.create_rest_routes", return_value=[]
        )

        agent = A2AServerAgent(agent=mock_agent, agent_card=card)
        agent.attach_app_server(Starlette())

        mock_create_jsonrpc.assert_not_called()
        mock_create_rest.assert_not_called()

    def test_create_http_routers_duplicate_protocol_skipped(
        self, mock_agent: MagicMock, mocker: MockerFixture
    ) -> None:
        card = _make_agent_card(
            interfaces=[
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                },
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                },
            ]
        )
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mock_create_jsonrpc = mocker.patch(
            "a2a_server.agent.create_jsonrpc_routes", return_value=[]
        )

        agent = A2AServerAgent(agent=mock_agent, agent_card=card)
        agent.attach_app_server(Starlette())

        mock_create_jsonrpc.assert_called_once()

    def test_create_http_routers_multiple_protocols(
        self, mock_agent: MagicMock, agent_card_multi: AgentCard, mocker: MockerFixture
    ) -> None:
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mock_create_jsonrpc = mocker.patch(
            "a2a_server.agent.create_jsonrpc_routes", return_value=[]
        )
        mock_create_rest = mocker.patch(
            "a2a_server.agent.create_rest_routes", return_value=[]
        )

        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_multi)
        agent.attach_app_server(Starlette())

        mock_create_jsonrpc.assert_called_once()
        mock_create_rest.assert_called_once()

    def test_create_http_routers_empty_interfaces_raises(
        self, mock_agent: MagicMock
    ) -> None:
        card = _make_agent_card(interfaces=[])
        agent = A2AServerAgent(agent=mock_agent, agent_card=card)
        with pytest.raises(Exception):
            agent.attach_app_server(Starlette())

    def test_extended_agent_card_passed(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mocker: MockerFixture,
    ) -> None:
        extended = _make_agent_card(name="extended")
        mock_handler_cls = mocker.patch("a2a_server.agent.DefaultRequestHandler")
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mocker.patch("a2a_server.agent.create_jsonrpc_routes", return_value=[])

        agent = A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            extended_agent_card=extended,
        )

        call_kwargs = mock_handler_cls.call_args.kwargs
        assert call_kwargs["extended_agent_card"] is extended

    def test_get_agent_card_success(
        self, mock_agent: MagicMock, agent_card_jsonrpc: AgentCard
    ) -> None:
        agent = A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
        )

        app = Starlette()
        agent.attach_app_server(app)
        client = TestClient(app)
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestA2AServerAgentClusterOptions:
    """共享存储参数（shared_storage / interrupted_task_timeout）。"""

    @pytest.fixture
    def mock_agent(self, mocker: MockerFixture) -> MagicMock:
        return mocker.MagicMock(spec=RunnableAgent)

    @pytest.fixture
    def agent_card_jsonrpc(self) -> AgentCard:
        return _make_agent_card(
            interfaces=[
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                }
            ]
        )

    @pytest.fixture
    def mock_handler_cls(self, mocker: MockerFixture) -> MagicMock:
        handler_cls = mocker.patch("a2a_server.agent.DefaultRequestHandler")
        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mocker.patch("a2a_server.agent.create_jsonrpc_routes", return_value=[])
        return handler_cls

    def test_default_uses_in_memory_task_store(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mock_handler_cls: MagicMock,
    ) -> None:
        """不传 shared_storage 时保持单机默认行为。"""

        A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)

        task_store = mock_handler_cls.call_args.kwargs["task_store"]
        assert isinstance(task_store, InMemoryTaskStore)

    def test_shared_storage_passed_to_handler(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mock_handler_cls: MagicMock,
    ) -> None:
        """SharedStorage 里的存储与事件流都透传给 handler。"""

        store = MagicMock(spec=VersionedTaskStore)
        stream = MagicMock(spec=TaskEventStream)
        storage = SharedStorage(task_store=store, event_stream=stream)

        A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            shared_storage=storage,
        )

        kwargs = mock_handler_cls.call_args.kwargs
        assert kwargs["task_store"] is store
        assert kwargs["event_stream"] is stream

    def test_event_stream_with_in_memory_store_raises(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        """event_stream 配进程内存储属于无效配置，应尽早报错。"""

        storage = SharedStorage(
            task_store=InMemoryTaskStore(),
            event_stream=MagicMock(spec=TaskEventStream),
        )

        with pytest.raises(ValueError, match="shared_storage"):
            A2AServerAgent(
                agent=mock_agent,
                agent_card=agent_card_jsonrpc,
                shared_storage=storage,
            )

    def test_versioned_store_without_event_stream_warns(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """只配版本化存储时提示跨副本事件流未启用。"""

        storage = SharedStorage(task_store=MagicMock(spec=VersionedTaskStore))

        with caplog.at_level(logging.WARNING):
            A2AServerAgent(
                agent=mock_agent,
                agent_card=agent_card_jsonrpc,
                shared_storage=storage,
            )

        assert "event_stream" in caplog.text

    def test_database_event_stream_requires_versioned_store(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        """DatabaseTaskEventStream 依赖事件日志表，普通 store 不会写它。

        配错了不会报错，只会静默收不到事件，所以要在构造期拦下。
        """

        from a2a.server.cluster import DatabaseTaskEventStream
        from a2a.server.tasks import DatabaseTaskStore

        storage = SharedStorage(
            task_store=MagicMock(spec=DatabaseTaskStore),
            event_stream=MagicMock(spec=DatabaseTaskEventStream),
        )

        with pytest.raises(ValueError, match="VersionedTaskStore"):
            A2AServerAgent(
                agent=mock_agent,
                agent_card=agent_card_jsonrpc,
                shared_storage=storage,
            )

    def test_plain_store_with_custom_event_stream_allowed(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mock_handler_cls: MagicMock,
    ) -> None:
        """自定义 stream 自己投递事件，普通 store 也可以配。"""

        from a2a.server.tasks import DatabaseTaskStore

        store = MagicMock(spec=DatabaseTaskStore)
        stream = MagicMock(spec=TaskEventStream)

        A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            shared_storage=SharedStorage(
                task_store=store, event_stream=stream
            ),
        )

        kwargs = mock_handler_cls.call_args.kwargs
        assert kwargs["task_store"] is store
        assert kwargs["event_stream"] is stream

    def test_interrupted_task_timeout_passed(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mock_handler_cls: MagicMock,
    ) -> None:
        """interrupted_task_timeout 透传给 handler。"""

        A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            interrupted_task_timeout=300,
        )

        assert mock_handler_cls.call_args.kwargs["interrupted_task_timeout"] == 300

    def test_interrupted_task_timeout_must_be_positive(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        with pytest.raises(ValueError, match="interrupted_task_timeout"):
            A2AServerAgent(
                agent=mock_agent,
                agent_card=agent_card_jsonrpc,
                interrupted_task_timeout=0,
            )


class TestA2AServerAgentLifecycle:
    """startup / shutdown 与 lifespan 挂载。"""

    @pytest.fixture
    def mock_agent(self, mocker: MockerFixture) -> MagicMock:
        return mocker.MagicMock(spec=RunnableAgent)

    @pytest.fixture
    def agent_card_jsonrpc(self) -> AgentCard:
        return _make_agent_card(
            interfaces=[
                {
                    "protocol_binding": PROTOCOL_JSON_RPC,
                    "url": "http://localhost/jsonrpc",
                }
            ]
        )

    @pytest.mark.asyncio
    async def test_startup_initializes_store_and_stream(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        store = MagicMock(spec=VersionedTaskStore)
        store.initialize = AsyncMock()
        stream = MagicMock(spec=TaskEventStream)
        stream.initialize = AsyncMock()

        agent = A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            shared_storage=SharedStorage(
                task_store=store, event_stream=stream
            ),
        )

        await agent.startup()

        store.initialize.assert_awaited_once()
        stream.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_startup_is_idempotent(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        store = MagicMock(spec=VersionedTaskStore)
        store.initialize = AsyncMock()

        agent = A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            shared_storage=SharedStorage(
                task_store=store,
                event_stream=MagicMock(spec=TaskEventStream),
            ),
        )

        await agent.startup()
        await agent.startup()

        store.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_startup_after_shutdown_reinitializes(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        """stop 之后再次 start，存储应被重新初始化。"""

        store = MagicMock(spec=VersionedTaskStore)
        store.initialize = AsyncMock()

        agent = A2AServerAgent(
            agent=mock_agent,
            agent_card=agent_card_jsonrpc,
            shared_storage=SharedStorage(
                task_store=store,
                event_stream=MagicMock(spec=TaskEventStream),
            ),
        )

        await agent.startup()
        await agent.shutdown()
        await agent.startup()

        assert store.initialize.await_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mocker: MockerFixture,
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        aclose = mocker.patch.object(
            agent.request_handler(), "aclose", new=AsyncMock()
        )

        await agent.shutdown()
        await agent.shutdown()

        aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_closes_handler(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mocker: MockerFixture,
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        aclose = mocker.patch.object(agent.request_handler(), "aclose", new=AsyncMock())

        await agent.shutdown()

        aclose.assert_awaited_once()

    def test_lifespan_calls_startup_and_shutdown(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
        mocker: MockerFixture,
    ) -> None:
        """挂载到 app 后，进入 lifespan 会启动、退出时会关闭。"""

        mocker.patch("a2a_server.agent.create_agent_card_routes", return_value=[])
        mocker.patch("a2a_server.agent.create_jsonrpc_routes", return_value=[])

        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        startup = mocker.patch.object(agent, "startup", new=AsyncMock())
        shutdown = mocker.patch.object(agent, "shutdown", new=AsyncMock())

        app = Starlette()
        agent.attach_app_server(app)

        with TestClient(app):
            startup.assert_awaited_once()
            shutdown.assert_not_awaited()

        shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(
        self,
        mock_agent: MagicMock,
        agent_card_jsonrpc: AgentCard,
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)

        async with agent as entered:
            assert entered is agent
