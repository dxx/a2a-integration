from google.protobuf import json_format, struct_pb2

import pytest

from a2a_client.context import build_call_context, build_metadata, RequestContext
from a2a.client import ClientCallContext


class TestBuildCallContext:
    def test_with_header_parameters(self) -> None:
        ctx = RequestContext(header_parameters={"X-Api-Key": "secret"})
        result = build_call_context(ctx)

        assert isinstance(result, ClientCallContext)
        assert result.service_parameters == {"X-Api-Key": "secret"}

    def test_with_none_header_parameters(self) -> None:
        ctx = RequestContext(header_parameters=None)
        result = build_call_context(ctx)

        assert isinstance(result, ClientCallContext)
        assert result.service_parameters is None


class TestBuildMetadata:
    def test_with_request_metadata(self) -> None:
        ctx = RequestContext(request_metadata={"task_id": "123", "user": "test"})
        result = build_metadata(ctx)

        assert isinstance(result, struct_pb2.Struct)
        assert json_format.MessageToDict(result) == {"task_id": "123", "user": "test"}

    def test_with_none_request_metadata(self) -> None:
        ctx = RequestContext(request_metadata=None)
        with pytest.raises(json_format.ParseError):
            build_metadata(ctx)

    def test_with_empty_request_metadata(self) -> None:
        ctx = RequestContext(request_metadata={})
        result = build_metadata(ctx)

        assert isinstance(result, struct_pb2.Struct)
        assert json_format.MessageToDict(result) == {}
