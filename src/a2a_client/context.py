from typing import Any
from dataclasses import dataclass
from google.protobuf import struct_pb2, json_format
from a2a.client import ClientCallContext


@dataclass
class RequestContext:
    """请求信息的上下文。"""

    header_parameters: dict[str, str] | None = None
    """HTTP 请求头参数或 GRPC 的 metadata 的参数。

    See: https://a2a-protocol.org/latest/specification/#326-service-parameters
    """

    request_metadata: dict[str, Any] | None = None
    """SendMessageRequest 参数中的 metadata 内容。

    see: https://a2a-protocol.org/latest/specification/#325-metadata
    """


def build_call_context(context: RequestContext) -> ClientCallContext :
    return ClientCallContext(
        service_parameters=context.header_parameters
    )

def build_metadata(context: RequestContext) -> struct_pb2.Struct:
    return json_format.ParseDict(context.request_metadata, struct_pb2.Struct())
