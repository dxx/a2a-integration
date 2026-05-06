from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from a2a_server.context import (
    build_request_context,
    RequestContext,
    _get_metadata_values,
)


@pytest.fixture
def make_context(mocker: MockerFixture):
    def _make(params=None, state=None):
        mock_call_context = mocker.MagicMock()
        mock_call_context.state = state or {}
        mock_request_context = mocker.MagicMock()
        mock_request_context.call_context = mock_call_context
        mock_request_context._params = params
        return mock_request_context

    return _make


class TestBuildRequestContext:
    def test_build_with_headers_and_metadata(
        self, mocker: MockerFixture, make_context
    ) -> None:
        mock_msg_to_dict = mocker.patch("a2a_server.context.json_format.MessageToDict")
        mock_metadata = mocker.MagicMock()
        mock_params = mocker.MagicMock()
        mock_params.metadata = mock_metadata

        mock_context = make_context(
            params=mock_params, state={"headers": {"X-Api-Key": "secret"}}
        )
        mock_msg_to_dict.return_value = {"task_id": "123"}

        result = build_request_context(mock_context)

        assert isinstance(result, RequestContext)
        assert result.header_parameters == {"X-Api-Key": "secret"}
        assert result.request_metadata == {"task_id": "123"}
        mock_msg_to_dict.assert_called_once_with(mock_metadata)

    def test_build_without_params(self, make_context) -> None:
        mock_context = make_context(params=None, state={})

        result = build_request_context(mock_context)

        assert result.header_parameters == {}
        assert result.request_metadata == {}

    def test_build_with_empty_metadata(
        self, mocker: MockerFixture, make_context
    ) -> None:
        mock_params = mocker.MagicMock()
        mock_params.metadata = None
        mock_context = make_context(params=mock_params, state={"headers": {}})

        result = build_request_context(mock_context)

        assert result.header_parameters == {}
        assert result.request_metadata == {}

    def test_build_with_grpc_context(self, mocker: MockerFixture, make_context) -> None:
        mock_get_metadata = mocker.patch("a2a_server.context._get_metadata_values")
        mock_grpc_ctx = mocker.MagicMock()
        mock_context = make_context(params=None, state={"grpc_context": mock_grpc_ctx})
        mock_get_metadata.return_value = {"grpc-auth": "token"}

        result = build_request_context(mock_context)

        assert result.header_parameters == {"grpc-auth": "token"}
        assert result.request_metadata == {}
        mock_get_metadata.assert_called_once_with(mock_grpc_ctx)

    def test_build_no_headers_no_grpc(
        self, mocker: MockerFixture, make_context
    ) -> None:
        mock_params = mocker.MagicMock()
        mock_params.metadata = None
        mock_context = make_context(params=mock_params, state={})

        result = build_request_context(mock_context)

        assert result.header_parameters == {}
        assert result.request_metadata == {}


class TestGetMetadataValues:
    def test_with_string_and_bytes(self, mocker: MockerFixture) -> None:
        mock_grpc_context = mocker.MagicMock()
        mock_grpc_context.invocation_metadata.return_value = [
            ("key1", b"value1"),
            ("key2", "value2"),
        ]

        result = _get_metadata_values(mock_grpc_context)

        assert result == {"key1": "value1", "key2": "value2"}

    def test_with_none_metadata(self, mocker: MockerFixture) -> None:
        mock_grpc_context = mocker.MagicMock()
        mock_grpc_context.invocation_metadata.return_value = None

        result = _get_metadata_values(mock_grpc_context)

        assert result == {}
