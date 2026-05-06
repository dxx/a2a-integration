from typing import Any
from dataclasses import dataclass
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.context import ServerCallContext
from a2a.server.agent_execution.context import RequestContext as A2ARequestContext
from starlette.requests import Request
from google.protobuf import json_format
from a2a.types.a2a_pb2 import SendMessageRequest


class HTTPRestStreamingAwareContextBuilder(DefaultServerCallContextBuilder):
    """继承 DefaultServerCallContextBuilder，根据请求 path 判断是否流式请求。"""

    def build(self, request: Request) -> ServerCallContext:
        context = super().build(request)
        path = request.url.path
        # 获取最后一段 path（包含 /）
        last_segment = "/" + path.rsplit("/", 1)[-1]
        context.state["method"] = last_segment
        return context


@dataclass
class RequestContext:
    """包含一些请求信息的上下文。"""

    header_parameters: dict[str, str]
    """HTTP 请求头参数或 GRPC 的 metadata 的参数。

    See: https://a2a-protocol.org/latest/specification/#326-service-parameters
    """

    request_metadata: dict[str, Any]
    """SendMessageRequest 参数中的 metadata 内容。

    see: https://a2a-protocol.org/latest/specification/#325-metadata
    """


def build_request_context(context: A2ARequestContext) -> RequestContext:
    # request_metadata = context.metadata
    request_metadata = {}
    params: SendMessageRequest = getattr(context, "_params")
    if params and params.metadata:
        request_metadata = json_format.MessageToDict(params.metadata)
    
    header_parameters = {}

    # 提取 headers 参数
    headers = context.call_context.state.get("headers", None)
    if headers:
        header_parameters = headers
    else:
        # 从 GRPC 上下文中提取参数
        grpc_context = context.call_context.state.get("grpc_context", None)
        if grpc_context:
            header_parameters = _get_metadata_values(grpc_context)
    
    return RequestContext(header_parameters, request_metadata)


def _get_metadata_values(context) -> dict[str, str]:
    """从 grpc.aio.ServicerContext 提取 metadata。"""
    
    md = context.invocation_metadata()
    if md is None:
        return {}

    return {
            k:e if isinstance(e, str) else e.decode('utf-8')
            for k, e in md
        }
    