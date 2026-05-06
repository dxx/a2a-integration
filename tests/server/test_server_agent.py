from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from starlette.applications import Starlette
from starlette.testclient import TestClient

from a2a.types import AgentCard
from a2a.server.request_handlers import RequestHandler
from a2a_server.agent import (
    A2AServerAgent,
    RunnableAgent,
)
from a2a_common.constants import PROTOCOL_JSON_RPC, PROTOCOL_HTTP_JSON, PROTOCOL_GRPC


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

    def test_init_server_app_returns_starlette(
        self, mock_agent: MagicMock, agent_card_jsonrpc: AgentCard
    ) -> None:
        agent = A2AServerAgent(agent=mock_agent, agent_card=agent_card_jsonrpc)
        app = agent.init_server_app()
        assert isinstance(app, Starlette)

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
        agent.init_server_app()

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
        agent.init_server_app()

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
        agent.init_server_app()

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
        agent.init_server_app()

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
        agent.init_server_app()

        mock_create_jsonrpc.assert_called_once()
        mock_create_rest.assert_called_once()

    def test_create_http_routers_empty_interfaces_raises(
        self, mock_agent: MagicMock
    ) -> None:
        card = _make_agent_card(interfaces=[])
        agent = A2AServerAgent(agent=mock_agent, agent_card=card)
        with pytest.raises(Exception):
            agent.init_server_app()

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

        app = agent.init_server_app()
        client = TestClient(app)
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
